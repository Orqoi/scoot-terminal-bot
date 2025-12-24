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

# =====================
# CONFIG
# =====================
load_dotenv()
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))  # convert to int

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

# Persistent disk path
DB_PATH = "/data/auction.db"  # replace with your Render mount path
SCHEMA_FILE = "schema.sql"

# Ensure directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Connect to SQLite (file on persistent disk)
DB = sqlite3.connect(DB_PATH, check_same_thread=False)
DB.row_factory = sqlite3.Row  # optional, allows dict-like access


# Check if tables exist
def initialize_db():
    cursor = DB.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auctions';")
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        logger.info("DB empty — initializing schema from schema.sql")
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            DB.executescript(f.read())
        DB.commit()
    else:
        logger.info("DB already initialized — skipping schema creation")

initialize_db()

def now() -> int:
    return int(time.time())

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

    parts = caption.split()
    if len(parts) < 7:
        await msg.reply_text(
            "Usage:\n"
            "/sa SB RP MinInc DurationMin AntiSnipeMin Description"
        )
        return

    try:
        sb, rp, min_inc, duration, anti = map(int, parts[1:6])
        description = " ".join(parts[6:])
    except ValueError:
        await msg.reply_text("❌ Invalid numeric values.")
        return

    photo_id = msg.photo[-1].file_id
    end_time = now() + duration * 60

    caption_text = (
        f"🛒 <b>New Auction</b>\n\n"
        f"{description}\n\n"
        f"💰 SB: {sb}\n"
        f"🏷 RP: {rp}\n"
        f"➕ Min Inc: {min_inc}\n"
        f"⏱ Ends: <b>{time.strftime('%H:%M:%S', time.localtime(end_time))}</b>\n"
        f"🛡 Anti-snipe: {anti} min\n\n"
        f"💬 Comment with a number to bid"
    )

    sent = await context.bot.send_photo(
        chat_id=CHANNEL_ID,
        photo=photo_id,
        caption=caption_text,
        parse_mode="HTML",
    )

    # insert description into DB
    DB.execute(
        """
        INSERT INTO auctions (
            channel_post_id,
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
        VALUES (?, ?, ?, ?, ?, ?, 0, NULL, 'LIVE', ?)
        """,
        (sent.message_id, sb, rp, min_inc, end_time, anti, description),
    )
    DB.commit()

    logger.info("Auction started for channel post %s", sent.message_id)
    await msg.reply_text("✅ Auction posted to channel.")

# =====================
# BID HANDLER
# =====================
async def handle_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text or not msg.reply_to_message:
        return

    # numeric-only bids
    if not re.fullmatch(r"\d+", msg.text.strip()):
        return

    bid = int(msg.text.strip())

    origin = msg.reply_to_message.forward_origin
    if not origin or origin.type != MessageOriginType.CHANNEL:
        return

    if origin.chat.id != CHANNEL_ID:
        return

    channel_post_id = origin.message_id
    logger.info("Bid detected for channel post %s: %s", channel_post_id, bid)

    row = DB.execute(
        """
        SELECT sb, rp, min_inc, end_time, anti_snipe, highest_bid, highest_bidder, description
        FROM auctions
        WHERE channel_post_id = ?
        """,
        (channel_post_id,),
    ).fetchone()

    if not row:
        return

    sb, rp, min_inc, end_time, anti, highest, highest_bidder, description = row
    if now() > end_time or highest is None:
        await msg.delete()
        return

    min_valid = sb if highest == 0 else highest + min_inc
    if bid < min_valid:
        await msg.delete()
        return

    # anti-snipe logic
    if now() >= end_time - anti * 60:
        end_time += anti * 60
        await msg.reply_text(f"⏱ Anti-snipe! Extended by {anti} min")

    # update DB
    DB.execute(
        """
        UPDATE auctions
        SET highest_bid = ?, highest_bidder = ?, end_time = ?
        WHERE channel_post_id = ?
        """,
        (bid, msg.from_user.id, end_time, channel_post_id),
    )
    DB.commit()

    # update channel caption with SB, RP, MinInc
    bidder_name = msg.from_user.first_name or "User"
    new_caption = (
        f"🛒 <b>New Auction</b>\n\n"
        f"{description}\n\n"
        f"💰 SB: {sb}\n"
        f"🏷 RP: {rp}\n"
        f"➕ Min Inc: {min_inc}\n"
        f"🛡 Anti-snipe: {anti} min\n\n"
        f"💰 Current bid: <b>{bid}</b>\n"
        f"👤 Bidder: <a href='tg://user?id={msg.from_user.id}'>{bidder_name}</a>\n"
        f"⏱ Ends: <b>{time.strftime('%H:%M:%S', time.localtime(end_time))}</b>"
    )

    await context.bot.edit_message_caption(
        chat_id=CHANNEL_ID,
        message_id=channel_post_id,
        caption=new_caption,
        parse_mode="HTML",
    )

    logger.info(
        "Bid %s accepted on post %s by %s",
        bid,
        channel_post_id,
        bidder_name,
    )

# =====================
# AUCTION END CHECK
# =====================
async def check_auctions(app):
    rows = DB.execute(
        """
        SELECT auction_id, channel_post_id, rp, highest_bid, highest_bidder, description
        FROM auctions
        WHERE status = 'LIVE' AND end_time <= ?
        """,
        (now(),),
    ).fetchall()

    for auction_id, post_id, rp, bid, bidder, description in rows:
        DB.execute(
            "UPDATE auctions SET status = 'ENDED' WHERE auction_id = ?",
            (auction_id,),
        )
        DB.commit()

        if bid >= rp and bidder:
            # fetch user's first name for display
            user = await app.bot.get_chat(bidder)
            bidder_name = user.first_name or "User"
            caption = (
                f"🏁 <b>Auction Ended</b>\n\n"
                f"{description}\n\n"
                f"Winning bid: <b>{bid}</b>\n"
                f"👤 <a href='tg://user?id={bidder}'>{bidder_name}</a>"
            )
        else:
            caption = (
                f"🏁 <b>Auction Ended</b>\n\n"
                f"{description}\n\n"
                f"❌ Reserve not met."
            )

        await app.bot.edit_message_caption(
            chat_id=CHANNEL_ID,
            message_id=post_id,
            caption=caption,
            parse_mode="HTML",
        )

        logger.info("Auction %s ended", auction_id)

# =====================
# SUMMARY HANDLER
# =====================
async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    rows = DB.execute(
        """
        SELECT description, sb, highest_bid, highest_bidder, end_time
        FROM auctions
        WHERE status = 'LIVE'
        ORDER BY end_time ASC
        """
    ).fetchall()

    if not rows:
        await msg.reply_text("No live auctions.")
        return

    lines = ["📊 <b>Live Auction Summary</b>\n"]

    for description, sb, bid, bidder, end_time in rows:
        short_desc = (description[:40] + "...") if len(description) > 40 else description
        current_bid = bid if bid > 0 else sb

        if bidder:
            user = await context.bot.get_chat(bidder)
            bidder_name = user.first_name or "User"
            bidder_text = f"<a href='tg://user?id={bidder}'>{bidder_name}</a>"
        else:
            bidder_text = "—"

        lines.append(
            f"💬 <b>{short_desc}</b>\n"
            f"💰 Current bid: <b>{current_bid}</b>\n"
            f"👤 Bidder: {bidder_text}\n"
            f"⏱ Ends: {time.strftime('%H:%M:%S', time.localtime(end_time))}\n"
        )

    summary_text = "\n".join(lines)

    await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=summary_text,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )

    logger.info("Summary posted to channel by %s", msg.from_user.id)

# =====================
# MAIN
# =====================
from apscheduler.schedulers.asyncio import AsyncIOScheduler

async def on_startup(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_auctions, "interval", seconds=15, args=[app])
    scheduler.start()

    app.bot_data["scheduler"] = scheduler
    logger.info("APScheduler started inside PTB event loop")

def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(on_startup)   # <-- THIS is the fix
        .build()
    )

    app.add_handler(CommandHandler("summary", handle_summary))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.GROUPS, handle_newauction))
    app.add_handler(MessageHandler(filters.TEXT, handle_bid))

    logger.info("🤖 Auction bot running")
    app.run_polling()

if __name__ == "__main__":
    main()
