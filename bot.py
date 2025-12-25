import sqlite3
import time
import re
import logging
import os
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.constants import MessageOriginType
from datetime import datetime, timezone, timedelta

SG_TZ = timezone(timedelta(hours=8))

# =====================
# CONFIG
# =====================
load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

# =====================
# LOGGING
# =====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("auction-bot")

# =====================
# DATABASE
# =====================
DB = sqlite3.connect("/data/auction.db", check_same_thread=False)
DB.execute(open("schema.sql", "r", encoding="utf-8").read())
DB.commit()


def now() -> int:
    return int(time.time())


def parse_end_time(duration_or_time: str) -> int:
    """Convert duration in minutes or datetime string to UNIX timestamp"""
    try:
        # Try as integer minutes
        minutes = int(duration_or_time)
        return now() + minutes * 60
    except ValueError:
        # Try as datetime string
        dt = datetime.strptime(duration_or_time, "%Y-%m-%d %H:%M")
        return int(dt.replace(tzinfo=SG_TZ).timestamp())


# =====================
# AUCTION CREATION
# =====================
async def handle_newauction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.photo:
        return

    caption = (msg.caption or "").strip()
    if not caption.startswith("/sa"):
        return

    # /sa "Title" SB RP MinInc DurationOrEnd AntiSnipeMin "Description"
    m = re.match(
        r'^/sa\s+"(.+?)"\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+"(.+)"$',
        caption,
        re.S,
    )

    if not m:
        await msg.reply_text(
            'Usage:\n'
            '/sa "Title" SB RP MinInc DurationOrEnd AntiSnipeMin "Description"\n'
            'DurationOrEnd: either minutes (e.g., 60) or end datetime YYYY-MM-DD HH:MM'
        )
        return

    title = m.group(1)
    sb = int(m.group(2))
    rp = int(m.group(3))
    min_inc = int(m.group(4))
    duration_or_end = m.group(5)
    anti = int(m.group(6))
    description = m.group(7)

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

    logger.info("Auction started for channel post %s", sent.message_id)
    await msg.reply_text("✅ Auction posted to channel.")


# =====================
# SCHEDULED AUCTION
# =====================
async def handle_scheduleauction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.photo:
        return

    caption = (msg.caption or "").strip()
    if not caption.startswith("/schedulesa"):
        return

    # /schedulesa "Title" SB RP MinInc "StartTime" DurationOrEnd AntiSnipeMin "Description"
    m = re.match(
        r'^/schedulesa\s+"(.+?)"\s+(\d+)\s+(\d+)\s+(\d+)\s+"(.+?)"\s+(\S+)\s+(\d+)\s+"(.+)"$',
        caption,
        re.S,
    )

    if not m:
        await msg.reply_text(
            'Usage:\n'
            '/schedulesa "Title" SB RP MinInc "StartTime" DurationOrEnd AntiSnipeMin "Description"\n'
            'StartTime: YYYY-MM-DD HH:MM\n'
            'DurationOrEnd: either minutes or end datetime YYYY-MM-DD HH:MM'
        )
        return

    title = m.group(1)
    sb = int(m.group(2))
    rp = int(m.group(3))
    min_inc = int(m.group(4))
    start_time_str = m.group(5)
    duration_or_end = m.group(6)
    anti = int(m.group(7))
    description = m.group(8)

    start_timestamp = int(datetime.strptime(start_time_str, "%Y-%m-%d %H:%M").replace(tzinfo=SG_TZ).timestamp())
    end_time = parse_end_time(duration_or_end)

    photo_id = msg.photo[-1].file_id

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
        logger.info("Scheduled auction posted for channel post %s", sent.message_id)

    scheduler.add_job(post_auction, "date", run_date=start_timestamp)
    await msg.reply_text(f"✅ Auction scheduled to start at {start_time_str}")


# =====================
# BID HANDLER
# =====================
async def handle_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text or not msg.reply_to_message:
        return

    text = msg.text.strip()
    if not (re.fullmatch(r"\d+", text) or text.lower() == "sb"):
        return

    origin = msg.reply_to_message.forward_origin
    if not origin or origin.type != MessageOriginType.CHANNEL:
        return

    if origin.chat.id != CHANNEL_ID:
        return

    channel_post_id = origin.message_id

    row = DB.execute(
        """
        SELECT title, sb, rp, min_inc, end_time, anti_snipe, highest_bid, highest_bidder, description
        FROM auctions
        WHERE channel_post_id = ?
        """,
        (channel_post_id,),
    ).fetchone()

    if not row:
        return

    title, sb, rp, min_inc, end_time, anti, highest, highest_bidder, description = row

    if now() > end_time or highest is None:
        await msg.delete()
        return

    if text.lower() == "sb":
        bid = sb if highest == 0 else highest + min_inc
    else:
        bid = int(text)

    min_valid = sb if highest == 0 else highest + min_inc
    if bid < min_valid:
        await msg.delete()
        return

    if now() >= end_time - anti * 60:
        end_time += anti * 60
        await msg.reply_text(f"⏱ Anti-snipe! Extended by {anti} min")

    DB.execute(
        """
        UPDATE auctions
        SET highest_bid = ?, highest_bidder = ?, end_time = ?
        WHERE channel_post_id = ?
        """,
        (bid, msg.from_user.id, end_time, channel_post_id),
    )
    DB.commit()

    bidder_name = msg.from_user.first_name or "User"
    new_caption = (
        f"🛒 <b>{title}</b>\n\n"
        f"{description}\n\n"
        f"💰 SB: {sb}\n"
        f"🏷 RP: {rp}\n"
        f"➕ Min Inc: {min_inc}\n"
        f"🛡 Anti-snipe: {anti} min\n\n"
        f"💰 Current bid: <b>{bid}</b>\n"
        f"👤 Bidder: <a href='tg://user?id={msg.from_user.id}'>{bidder_name}</a>\n"
        f"⏱ Ends: <b>{datetime.fromtimestamp(end_time, tz=SG_TZ).strftime('%Y-%m-%d %H:%M')}</b>"
    )

    await context.bot.edit_message_caption(
        chat_id=CHANNEL_ID,
        message_id=channel_post_id,
        caption=new_caption,
        parse_mode="HTML",
    )


# =====================
# AUCTION END CHECK
# =====================
async def check_auctions(app):
    rows = DB.execute(
        """
        SELECT auction_id, channel_post_id, title, rp, highest_bid, highest_bidder, description
        FROM auctions
        WHERE status = 'LIVE' AND end_time <= ?
        """,
        (now(),),
    ).fetchall()

    for auction_id, post_id, title, rp, bid, bidder, description in rows:
        DB.execute(
            "UPDATE auctions SET status = 'ENDED' WHERE auction_id = ?",
            (auction_id,),
        )
        DB.commit()

        if bid >= rp and bidder:
            user = await app.bot.get_chat(bidder)
            bidder_name = user.first_name or "User"
            caption = (
                f"🏁 <b>{title} — Auction Ended</b>\n\n"
                f"{description}\n\n"
                f"Winning bid: <b>{bid}</b>\n"
                f"👤 <a href='tg://user?id={bidder}'>{bidder_name}</a>"
            )
        else:
            caption = (
                f"🏁 <b>{title} — Auction Ended</b>\n\n"
                f"{description}\n\n"
                f"❌ Reserve not met."
            )

        await app.bot.edit_message_caption(
            chat_id=CHANNEL_ID,
            message_id=post_id,
            caption=caption,
            parse_mode="HTML",
        )


# =====================
# SUMMARY
# =====================
async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    rows = DB.execute(
        """
        SELECT title, description, sb, highest_bid, highest_bidder, end_time
        FROM auctions
        WHERE status = 'LIVE'
        ORDER BY end_time ASC
        """
    ).fetchall()

    if not rows:
        await msg.reply_text("No live auctions.")
        return

    lines = ["📊 <b>Live Auction Summary</b>\n"]

    for title, description, sb, bid, bidder, end_time in rows:
        current_bid = bid if bid > 0 else sb

        if bidder:
            user = await context.bot.get_chat(bidder)
            bidder_name = user.first_name or "User"
            bidder_text = f"<a href='tg://user?id={bidder}'>{bidder_name}</a>"
        else:
            bidder_text = "—"

        lines.append(
            f"🛒 <b>{title}</b>\n"
            f"{description}\n"
            f"💰 Current bid: <b>{current_bid}</b>\n"
            f"👤 {bidder_text}\n"
            f"⏱ Ends: {datetime.fromtimestamp(end_time, tz=SG_TZ).strftime('%Y-%m-%d %H:%M')}\n"
        )

    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text="\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


# =====================
# MAIN
# =====================
async def on_startup(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_auctions, "interval", seconds=15, args=[app])
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info("Scheduler started")


def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(on_startup)
        .build()
    )

    app.add_handler(CommandHandler("summary", handle_summary))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.GROUPS, handle_newauction))
    app.add_handler(MessageHandler(filters.TEXT, handle_bid))
    app.add_handler(MessageHandler(filters.PHOTO & filters.Regex(r'^/schedulesa'), handle_scheduleauction))

    logger.info("🤖 Auction bot running")
    app.run_polling()


if __name__ == "__main__":
    main()
