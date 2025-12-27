from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import SG_TZ
from db.connection import DB

async def handle_view_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    rows = DB.execute(
        """
        SELECT auction_id, title, description, sb, rp, min_inc, start_time, end_time, anti_snipe, channel_id
        FROM auctions
        WHERE status = 'SCHEDULED' AND owner_user_id = ?
        ORDER BY start_time ASC
        """,
        (msg.from_user.id,),
    ).fetchall()

    if not rows:
        await msg.reply_text("You have no scheduled auctions.")
        return

    lines = ["📅 <b>Your Scheduled Auctions</b>\n"]

    for auction_id, title, description, sb, rp, min_inc, start_time, end_time, anti, channel_id in rows:
        lines.append(
            f"🆔 ID: <code>{auction_id}</code>\n"
            f"🛒 <b>{title}</b>\n"
            f"{description}\n"
            f"📍 Channel: <code>{channel_id}</code>\n"
            f"⏰ Starts: <b>{datetime.fromtimestamp(start_time, tz=SG_TZ).strftime('%Y-%m-%d %H:%M')}</b>\n"
            f"⏱ Ends: <b>{datetime.fromtimestamp(end_time, tz=SG_TZ).strftime('%Y-%m-%d %H:%M')}</b>\n"
            f"💰 SB: {sb} | 🏷 RP: {rp} | ➕ Min Inc: {min_inc}\n"
            f"🛡 Anti-snipe: {anti} min\n"
        )

    await msg.reply_text("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)