from telegram.ext import Application
from db.connection import DB
from utils.time import now

async def check_auctions(app: Application):
    rows = DB.execute(
        """
        SELECT auction_id, channel_id, channel_post_id, title, rp, highest_bid, highest_bidder, description,
               reply_chat_id, reply_message_id
        FROM auctions
        WHERE status = 'LIVE' AND end_time <= ?
        """,
        (now(),),
    ).fetchall()

    for auction_id, chan_id, post_id, title, rp, bid, bidder, description, reply_chat_id, reply_message_id in rows:
        DB.execute(
            "UPDATE auctions SET status = 'ENDED' WHERE auction_id = ?",
            (auction_id,),
        )
        DB.commit()

        if bid >= rp and bidder:
            try:
                user = await app.bot.get_chat(bidder)
                bidder_name = user.first_name or "User"
                username = getattr(user, "username", None)
            except Exception:
                bidder_name = "User"
                username = None

            mention_text = f"@{username}" if username else f"<a href='tg://user?id={bidder}'>{bidder_name}</a>"
            caption = (
                f"🏁 <b>{title} — Auction Ended</b>\n\n"
                f"{description}\n\n"
                f"Winning bid: <b>{bid}</b>\n"
                f"👤 {mention_text}"
            )
        else:
            caption = (
                f"🏁 <b>{title} — Auction Ended</b>\n\n"
                f"{description}\n\n"
                f"❌ Reserve not met."
            )

        await app.bot.edit_message_caption(
            chat_id=chan_id,
            message_id=post_id,
            caption=caption,
            parse_mode="HTML",
        )

        # Post winner mention in bidding group, replying to the anchor
        if bid >= rp and bidder and reply_chat_id and reply_message_id:
            try:
                await app.bot.send_message(
                    chat_id=reply_chat_id,
                    reply_to_message_id=reply_message_id,
                    text=f"🏆 Winner: {mention_text} with bid <b>{bid}</b>",
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception:
                # Fallback: send as a normal message if reply fails
                try:
                    await app.bot.send_message(
                        chat_id=reply_chat_id,
                        text=f"🏆 Winner: {mention_text} with bid <b>{bid}</b>",
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass