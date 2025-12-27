import re
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import MessageOriginType
from db.connection import DB
from config.settings import logger

async def handle_bind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    text = (msg.text or "").strip()
    tokens = text.split()

    # Require BIND_SECRET to be configured
    from config.settings import BIND_SECRET
    if not BIND_SECRET:
        await msg.reply_text("❌ Binding disabled. Set BIND_SECRET in .env.")
        return

    # Determine if binding via forwarded post or direct args
    forwarded = (
        msg.reply_to_message
        and msg.reply_to_message.forward_origin
        and msg.reply_to_message.forward_origin.type == MessageOriginType.CHANNEL
    )

    channel_id = None
    secret = None

    if forwarded:
        # Expect: /bind <secret> while replying to a forwarded channel post
        if len(tokens) >= 2:
            secret = tokens[1]
        else:
            await msg.reply_text("Usage: reply to a forwarded channel post with '/bind <secret>'.")
            return
        channel_id = msg.reply_to_message.forward_origin.chat.id
    else:
        # Expect: /bind <channel_id or @username> <secret> in private chat
        if len(tokens) >= 3:
            channel_arg = tokens[1]
            secret = tokens[2]
            if channel_arg.startswith("@"):
                try:
                    chat = await context.bot.get_chat(channel_arg)
                    channel_id = chat.id
                except Exception:
                    await msg.reply_text("❌ Failed to resolve channel username. Add the bot to the channel and try again.")
                    return
            else:
                try:
                    channel_id = int(channel_arg)
                    await context.bot.get_chat(channel_id)  # validate existence/permissions
                except Exception:
                    await msg.reply_text("❌ Invalid channel ID. Provide a numeric ID or @username.")
                    return
        else:
            await msg.reply_text("Usage: /bind <channel_id or @username> <secret>\nOr reply to a forwarded channel post with '/bind <secret>'.")
            return

    # Validate secret
    if secret != BIND_SECRET:
        await msg.reply_text("❌ Invalid secret.")
        return

    try:
        DB.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('channel_id', ?)", (str(channel_id),))
        DB.commit()
        context.application.bot_data["channel_id"] = channel_id
        await msg.reply_text(f"✅ Bound channel: {channel_id}")
        logger.info("Channel bound to %s", channel_id)
    except Exception as e:
        await msg.reply_text("❌ Failed to bind channel. Try again.")
        logger.warning("Failed to bind channel: %s", e)