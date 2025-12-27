from telegram import Update
from telegram.ext import ContextTypes
from db.connection import DB

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    tokens = text.split()
    if len(tokens) != 2 or tokens[0].lower() != "/cancel":
        await msg.reply_text("Usage: /cancel <auction_id>")
        return

    try:
        auction_id = int(tokens[1])
    except ValueError:
        await msg.reply_text("❌ Invalid auction ID.")
        return

    row = DB.execute(
        "SELECT status, owner_user_id FROM auctions WHERE auction_id = ?",
        (auction_id,),
    ).fetchone()

    if not row:
        await msg.reply_text("❌ Auction not found.")
        return

    status, owner = row
    if status != "SCHEDULED":
        await msg.reply_text("❌ Only scheduled auctions can be deleted.")
        return

    if owner != msg.from_user.id:
        await msg.reply_text("❌ You can only delete auctions you created.")
        return

    # Remove scheduled job if present
    try:
        scheduler = context.application.bot_data.get("scheduler")
        if scheduler:
            scheduler.remove_job(f"publish_{auction_id}")
    except Exception:
        pass

    cur = DB.execute(
        "DELETE FROM auctions WHERE auction_id = ? AND status = 'SCHEDULED' AND owner_user_id = ?",
        (auction_id, msg.from_user.id),
    )
    DB.commit()

    if cur.rowcount and cur.rowcount > 0:
        await msg.reply_text(f"✅ Deleted scheduled auction {auction_id}.")
    else:
        await msg.reply_text("❌ Failed to delete scheduled auction.")