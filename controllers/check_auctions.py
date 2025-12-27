from telegram.ext import Application
from db.connection import DB
from utils.time import now

async def check_auctions(app: Application):
    # Detect presence of single-column reply anchor to avoid legacy crashes
    try:
        cols = {row[1] for row in DB.execute("PRAGMA table_info(auctions)").fetchall()}
        has_anchor = ("reply_anchor" in cols)
    except Exception:
        has_anchor = False

    if has_anchor:
        rows = DB.execute(
            """
            SELECT auction_id, channel_id, channel_post_id, title, rp, highest_bid, highest_bidder, description, reply_anchor
            FROM auctions
            WHERE status = 'LIVE' AND end_time <= ?
            """,
            (now(),),
        ).fetchall()
    else:
        rows = DB.execute(
            """
            SELECT auction_id, channel_id, channel_post_id, title, rp, highest_bid, highest_bidder, description
            FROM auctions
            WHERE status = 'LIVE' AND end_time <= ?
            """,
            (now(),),
        ).fetchall()

    for row in rows:
        if has_anchor:
            auction_id, chan_id, post_id, title, rp, bid, bidder, description, reply_anchor = row
        else:
            auction_id, chan_id, post_id, title, rp, bid, bidder, description = row
            reply_anchor = None

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

        # Reply to the winner’s bid to trigger a notification
        if bid >= rp and bidder and reply_anchor:
            try:
                chat_id_str, msg_id_str = reply_anchor.split(":", 1)
                reply_chat_id = int(chat_id_str)
                reply_message_id = int(msg_id_str)
            except Exception:
                reply_chat_id = None
                reply_message_id = None

            if reply_chat_id and reply_message_id:
                try:
                    await app.bot.send_message(
                        chat_id=reply_chat_id,
                        reply_to_message_id=reply_message_id,
                        text=f"🏆 Winner: {mention_text} with bid <b>{bid}</b>",
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    try:
                        await app.bot.send_message(
                            chat_id=reply_chat_id,
                            text=f"🏆 Winner: {mention_text} with bid <b>{bid}</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                        )
                    except Exception:
                        pass