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
    start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M").replace(tzinfo=SG_TZ)
    end_time = parse_end_time(duration_or_end)

    photo_id = msg.photo[-1].file_id

    channel_id = context.application.bot_data.get("channel_id")
    if not channel_id:
        await msg.reply_text("❌ No channel bound. Use /bind in private chat.")
        return

    scheduler: AsyncIOScheduler = context.application.bot_data["scheduler"]

    async def post_auction():
        caption_text = (
            f"🛒 <b>{title}</b>\n\n"
            f"{description}\n\n"
            f"💰 SB: {sb}\n"
            f"🏷 RP: {rp}\n"
            f"➕ Min Inc: {min_inc}\n"
            f"⏱ Ends: <b>{datetime.fromtimestamp(end_time, tz=SG_TZ).strftime('%Y-%m-%d %H:%M')}</b>\n"
            f"🛡 Anti-snipe: {anti} min\n\n"
            f"💬 Comment with a number to bid (or 'SB')"
        )

        sent = await context.bot.send_photo(
            chat_id=channel_id,
            photo=photo_id,
            caption=caption_text,
            parse_mode="HTML",
        )

        DB.execute(
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
                description
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, 'LIVE', ?)
            """,
            (
                channel_id,
                sent.message_id,
                title,
                sb,
                rp,
                min_inc,
                end_time,
                anti,
                description,
            ),
        )
        DB.commit()

    scheduler.add_job(post_auction, "date", run_date=start_dt)
    await msg.reply_text(f"✅ Auction scheduled to start at {start_time_str}")