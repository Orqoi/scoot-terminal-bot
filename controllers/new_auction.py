import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import CHANNEL_ID, SG_TZ
from db.connection import DB
from utils.time import parse_end_time

async def handle_newauction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.photo:
        return

    caption = (msg.caption or "").strip()
    if not re.match(r'^/sa(\s|$)', caption):
        return

    m = re.match(
        r'^/sa\s+"(.+?)"\s+(\d+)\s+(\d+)\s+(\d+)\s+(?:"(.+?)"|(\d+))\s+(\d+)\s+"(.+)"$',
        caption,
        re.S,
    )
    if not m:
        await msg.reply_text(
            'Usage:\n'
            '/sa "Title" SB RP MinInc DurationOrEnd AntiSnipeMin "Description"\n'
            'DurationOrEnd: minutes (e.g., 60) or quoted datetime "YYYY-MM-DD HH:MM[:SS]"'
        )
        return

    title = m.group(1)
    sb = int(m.group(2))
    rp = int(m.group(3))
    min_inc = int(m.group(4))
    duration_or_end = m.group(5) or m.group(6)  # quoted datetime or minutes
    anti = int(m.group(7))
    description = m.group(8)

    photo_id = msg.photo[-1].file_id
    end_time = parse_end_time(duration_or_end)

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
        chat_id=CHANNEL_ID,
        photo=photo_id,
        caption=caption_text,
        parse_mode="HTML",
    )

    DB.execute(
        """
        INSERT INTO auctions (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, 'LIVE', ?)
        """,
        (
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

    await msg.reply_text("✅ Auction posted to channel.")