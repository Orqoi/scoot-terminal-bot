import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import MessageOriginType
from config.settings import SG_TZ
from db.connection import DB
from utils.time import now

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

    channel_post_id = origin.message_id
    origin_channel_id = origin.chat.id

    row = DB.execute(
        """
        SELECT channel_id, title, sb, rp, min_inc, end_time, anti_snipe, highest_bid, highest_bidder, description
        FROM auctions
        WHERE channel_id = ? AND channel_post_id = ?
        """,
        (origin_channel_id, channel_post_id),
    ).fetchone()

    if not row:
        return

    channel_id_row, title, sb, rp, min_inc, end_time, anti, highest, highest_bidder, description = row

    if now() > end_time or highest is None:
        return

    if text.lower() == "sb":
        if highest == 0:
            bid = sb
        else:
            return
    else:
        bid = int(text)

    min_valid = sb if highest == 0 else highest + min_inc
    if bid < min_valid:
        return

    if now() >= end_time - anti * 60:
        end_time += anti * 60
        await msg.reply_text(f"⏱ Anti-snipe! Extended by {anti} min")

    DB.execute(
        """
        UPDATE auctions
        SET highest_bid = ?, highest_bidder = ?, end_time = ?, reply_anchor = ?
        WHERE channel_id = ? AND channel_post_id = ?
        """,
        (
            bid,
            msg.from_user.id,
            end_time,
            f"{msg.chat.id}:{msg.message_id}",  # winner reply target (chat_id:message_id)
            channel_id_row,
            channel_post_id,
        ),
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
        chat_id=channel_id_row,
        message_id=channel_post_id,
        caption=new_caption,
        parse_mode="HTML",
    )