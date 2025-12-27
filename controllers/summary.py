from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import CHANNEL_ID, SG_TZ
from db.connection import DB

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