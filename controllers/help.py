from telegram import Update
from telegram.ext import ContextTypes

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    text = (
        "ℹ️ <b>Auction Bot Help</b>\n\n"
        "<b>Create Auction</b>\n"
        '/sa "Title" SB RP MinInc DurationOrEnd AntiSnipeMin "Description"\n'
        "- DurationOrEnd: minutes (e.g., 60) or datetime YYYY-MM-DD HH:MM\n"
        "- Example: /sa \"Cat shirt\" 10 100 5 60 1 \"Cotton tee\"\n\n"
        "<b>Schedule Auction</b>\n"
        '/schedulesa "Title" SB RP MinInc "StartTime" DurationOrEnd AntiSnipeMin "Description"\n'
        '- StartTime: "YYYY-MM-DD HH:MM"\n'
        "- DurationOrEnd: minutes (e.g., 60) or datetime YYYY-MM-DD HH:MM\n"
        '- Example: /schedulesa "LV Bag" 10 100 5 "2025-12-27 17:20" 60 1 "Vintage bag"\n\n'
        "<b>Bid</b>\n"
        "- Reply to the forwarded channel post in the group.\n"
        "- Send a number (your bid) or 'SB'.\n"
        "- 'SB' places the minimum valid next bid.\n\n"
        "<b>Summary</b>\n"
        "- /summary — posts a summary of live auctions to the channel.\n"
    )

    await msg.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)