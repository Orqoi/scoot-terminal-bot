from telegram import Update
from telegram.ext import ContextTypes

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    text = (
        "ℹ️ <b>Auction Bot Help</b>\n\n"
        "<b>Bind Channel</b>\n"
        "- /bind &lt;channel_id or @username&gt; &lt;secret&gt; — send in private chat.\n"
        "- Or reply to a forwarded channel post with '/bind &lt;secret&gt;'.\n"
        "- Configure <code>BIND_SECRET</code> in <code>.env</code>.\n\n"
        "<b>Create Auction</b>\n"
        'Send a photo to me (private) with caption:\n'
        '/sa "Title" SB RP MinInc DurationOrEnd AntiSnipeMin "Description"\n'
        "- DurationOrEnd: minutes (e.g., 60) or datetime YYYY-MM-DD HH:MM\n"
        "- Example: /sa \"Cat shirt\" 10 100 5 60 1 \"Cotton tee\"\n\n"
        "<b>Schedule Auction</b>\n"
        'Send a photo to me (private) with caption:\n'
        '/schedulesa "Title" SB RP MinInc "StartTime" DurationOrEnd AntiSnipeMin "Description"\n'
        '- StartTime: "YYYY-MM-DD HH:MM"\n'
        "- DurationOrEnd: minutes (e.g., 60) or datetime YYYY-MM-DD HH:MM\n\n"
        "<b>View Schedule</b>\n"
        "- /viewschedule — lists your scheduled auctions with IDs.\n\n"
        "<b>Cancel Scheduled</b>\n"
        "- /cancel &lt;auction_id&gt; — deletes your scheduled auction.\n\n"
        "<b>Bid</b>\n"
        "- In the group, reply to the forwarded channel post.\n"
        "- Send a number (your bid) or 'SB'.\n\n"
        "<b>Summary</b>\n"
        "- Send /summary in private — posts a summary to the bound channel.\n"
    )

    await msg.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)