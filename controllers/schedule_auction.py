import re
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import SG_TZ
from db.connection import DB
from utils.time import parse_end_time

async def handle_scheduleauction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.photo:
        return

    caption = (msg.caption or "").strip()
    if not re.match(r'^/schedulesa(\s|$)', caption):
        return

    m = re.match(
        r'^/schedulesa\s+"(.+?)"\s+(\d+)\s+(\d+)\s+(\d+)\s+"(.+?)"\s+(?:"(.+?)"|(\d+))\s+(\d+)\s+"(.+)"$',
        caption,
        re.S,
    )
    if not m:
        await msg.reply_text(
            'Usage:\n'
            '/schedulesa "Title" SB RP MinInc "StartTime" DurationOrEnd AntiSnipeMin "Description"\n'
            'StartTime: "YYYY-MM-DD HH:MM"\n'
            'DurationOrEnd: minutes (e.g., 60) or quoted datetime "YYYY-MM-DD HH:MM[:SS]"'
        )
        return

    title = m.group(1)
    sb = int(m.group(2))
    rp = int(m.group(3))
    min_inc = int(m.group(4))
    start_time_str = m.group(5)
    duration_or_end = m.group(6) or m.group(7)  # quoted datetime or minutes
    anti = int(m.group(8))
    description = m.group(9)

    # Use a datetime for run_date
    try:
        start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M").replace(tzinfo=SG_TZ)
    except ValueError:
        await msg.reply_text("❌ Invalid start time. Use YYYY-MM-DD HH:MM")
        return

    try:
        end_time = parse_end_time(duration_or_end)
    except ValueError as e:
        await msg.reply_text(str(e))
        return

    photo_id = msg.photo[-1].file_id

    # Per-user binding lookup ONLY
    row = DB.execute("SELECT channel_id FROM bindings WHERE user_id = ?", (msg.from_user.id,)).fetchone()
    channel_id = row[0] if row else None

    if not channel_id:
        await msg.reply_text("❌ No channel bound for you. Use /bind in private chat.")
        return

    scheduler: AsyncIOScheduler = context.application.bot_data["scheduler"]
    owner = msg.from_user.id

    # Persist scheduled auction
    cur = DB.execute(
        """
        INSERT INTO auctions (
            channel_id,
            channel_post_id,
            title,
            sb,
            rp,
            min_inc,
            end_time,
            anti_snipe,
            highest_bid,
            highest_bidder,
            status,
            description,
            owner_user_id,
            start_time,
            photo_file_id
        )
        VALUES (?, NULL, ?, ?, ?, ?, ?, ?, 0, NULL, 'SCHEDULED', ?, ?, ?, ?)
        """,
        (
            channel_id,
            title,
            sb,
            rp,
            min_inc,
            end_time,
            anti,
            description,
            owner,
            int(start_dt.timestamp()),
            photo_id,
        ),
    )
    DB.commit()
    auction_id = cur.lastrowid

    async def post_auction(a_id: int):
        row = DB.execute(
            """
            SELECT title, description, sb, rp, min_inc, end_time, anti_snipe, channel_id, photo_file_id
            FROM auctions
            WHERE auction_id = ? AND status = 'SCHEDULED'
            """,
            (a_id,),
        ).fetchone()
        if not row:
            return

        title2, description2, sb2, rp2, min_inc2, end_time2, anti2, chan_id2, photo2 = row

        caption_text = (
            f"🛒 <b>{title2}</b>\n\n"
            f"{description2}\n\n"
            f"💰 SB: {sb2}\n"
            f"🏷 RP: {rp2}\n"
            f"➕ Min Inc: {min_inc2}\n"
            f"⏱ Ends: <b>{datetime.fromtimestamp(end_time2, tz=SG_TZ).strftime('%Y-%m-%d %H:%M')}</b>\n"
            f"🛡 Anti-snipe: {anti2} min\n\n"
            f"💬 Comment with a number to bid (or 'SB')"
        )

        sent = await context.bot.send_photo(
            chat_id=chan_id2,
            photo=photo2,
            caption=caption_text,
            parse_mode="HTML",
        )

        DB.execute(
            "UPDATE auctions SET channel_post_id = ?, status = 'LIVE' WHERE auction_id = ?",
            (sent.message_id, a_id),
        )
        DB.commit()

    scheduler.add_job(
        post_auction,
        "date",
        run_date=start_dt,
        args=[auction_id],
        id=f"publish_{auction_id}",
        replace_existing=True,
    )
    await msg.reply_text(f"✅ Auction scheduled to start at {start_time_str}")