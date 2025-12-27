import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import MessageOriginType
from config.settings import SG_TZ, logger
from db.connection import DB
from utils.time import now

async def handle_bid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text or not msg.reply_to_message:
        if msg:
            logger.info(
                "handle_bid: ignored (missing fields) chat=%s user=%s has_text=%s has_reply=%s",
                getattr(msg.chat, "id", None),
                getattr(msg.from_user, "id", None),
                bool(msg.text),
                bool(msg.reply_to_message),
            )
        return

    text = msg.text.strip()
    if not (re.fullmatch(r"\d+", text) or text.lower() == "sb"):
        logger.info(
            "handle_bid: invalid text format chat=%s user=%s text=%r",
            msg.chat.id,
            msg.from_user.id,
            text,
        )
        return

    origin = msg.reply_to_message.forward_origin
    if not origin or origin.type != MessageOriginType.CHANNEL:
        logger.info(
            "handle_bid: reply is not a forwarded channel post chat=%s user=%s origin=%s",
            msg.chat.id,
            msg.from_user.id,
            getattr(origin, "type", None),
        )
        return

    channel_post_id = origin.message_id
    origin_channel_id = origin.chat.id
    logger.debug(
        "handle_bid: origin resolved channel_id=%s post_id=%s",
        origin_channel_id,
        channel_post_id,
    )

    row = DB.execute(
        """
        SELECT channel_id, title, sb, rp, min_inc, end_time, anti_snipe, highest_bid, highest_bidder, description
        FROM auctions
        WHERE channel_id = ? AND channel_post_id = ?
        """,
        (origin_channel_id, channel_post_id),
    ).fetchone()

    if not row:
        logger.info(
            "handle_bid: auction not found channel_id=%s post_id=%s",
            origin_channel_id,
            channel_post_id,
        )
        return

    channel_id_row, title, sb, rp, min_inc, end_time, anti, highest, highest_bidder, description = row

    if highest is None:
        logger.warning(
            "handle_bid: legacy highest_bid NULL channel_id=%s post_id=%s — treating as 0",
            channel_id_row,
            channel_post_id,
        )

    if now() > end_time or highest is None:
        logger.info(
            "handle_bid: ignored due to ended_or_null ended=%s null_highest=%s channel_id=%s post_id=%s",
            now() > end_time,
            highest is None,
            channel_id_row,
            channel_post_id,
        )
        return

    if text.lower() == "sb":
        if highest == 0:
            bid = sb
            logger.info(
                "handle_bid: SB accepted chat=%s user=%s bid=%s",
                msg.chat.id,
                msg.from_user.id,
                bid,
            )
        else:
            logger.info(
                "handle_bid: SB rejected (already started) chat=%s user=%s highest=%s",
                msg.chat.id,
                msg.from_user.id,
                highest,
            )
            return
    else:
        bid = int(text)
        logger.info(
            "handle_bid: numeric bid parsed chat=%s user=%s bid=%s",
            msg.chat.id,
            msg.from_user.id,
            bid,
        )

    min_valid = sb if highest == 0 else highest + min_inc
    if bid < min_valid:
        logger.info(
            "handle_bid: bid below minimum chat=%s user=%s bid=%s min_valid=%s highest=%s min_inc=%s",
            msg.chat.id,
            msg.from_user.id,
            bid,
            min_valid,
            highest,
            min_inc,
        )
        return

    if now() >= end_time - anti * 60:
        end_time += anti * 60
        logger.info(
            "handle_bid: anti-snipe extended chat=%s user=%s anti=%s new_end=%s",
            msg.chat.id,
            msg.from_user.id,
            anti,
            end_time,
        )
        await msg.reply_text(f"⏱ Anti-snipe! Extended by {anti} min")

    anchor = f"{msg.chat.id}:{msg.message_id}"
    try:
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
                anchor,
                channel_id_row,
                channel_post_id,
            ),
        )
        DB.commit()
        logger.info(
            "handle_bid: DB updated channel_id=%s post_id=%s bid=%s bidder=%s reply_anchor=%s",
            channel_id_row,
            channel_post_id,
            bid,
            msg.from_user.id,
            anchor,
        )
    except Exception as e:
        logger.exception(
            "handle_bid: DB update failed channel_id=%s post_id=%s error=%s",
            channel_id_row,
            channel_post_id,
            e,
        )
        return

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

    try:
        await context.bot.edit_message_caption(
            chat_id=channel_id_row,
            message_id=channel_post_id,
            caption=new_caption,
            parse_mode="HTML",
        )
        logger.info(
            "handle_bid: caption updated channel_id=%s post_id=%s",
            channel_id_row,
            channel_post_id,
        )
    except Exception as e:
        logger.exception(
            "handle_bid: caption update failed channel_id=%s post_id=%s error=%s",
            channel_id_row,
            channel_post_id,
            e,
        )