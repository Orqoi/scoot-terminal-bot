from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import SG_TZ
from db.connection import DB

async def handle_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # Per-user binding lookup ONLY
    row = DB.execute("SELECT channel_id FROM bindings WHERE user_id = ?", (msg.from_user.id,)).fetchone()
    channel_id = row[0] if row else None

    if not channel_id:
        await msg.reply_text("❌ No channel bound for you. Use /bind in private chat.")
        return

    rows = DB.execute(
        """
        SELECT title, description, sb, highest_bid, highest_bidder, end_time
        FROM auctions
        WHERE status = 'LIVE' AND channel_id = ?
        ORDER BY end_time ASC
        """,
        (channel_id,),
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
        chat_id=channel_id,
        text="\n".join(lines),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )