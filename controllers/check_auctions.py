from telegram.ext import Application
from db.connection import DB
from utils.time import now

async def check_auctions(app: Application):
    rows = DB.execute(
        """
        SELECT auction_id, channel_id, channel_post_id, title, rp, highest_bid, highest_bidder, description
        FROM auctions
        WHERE status = 'LIVE' AND end_time <= ?
        """,
        (now(),),
    ).fetchall()

    for auction_id, chan_id, post_id, title, rp, bid, bidder, description in rows:
        DB.execute(
            "UPDATE auctions SET status = 'ENDED' WHERE auction_id = ?",
            (auction_id,),
        )
        DB.commit()

        if bid >= rp and bidder:
            try:
                user = await app.bot.get_chat(bidder)
                bidder_name = user.first_name or "User"
            except Exception:
                bidder_name = "User"
            caption = (
                f"🏁 <b>{title} — Auction Ended</b>\n\n"
                f"{description}\n\n"
                f"Winning bid: <b>{bid}</b>\n"
                f"👤 <a href='tg://user?id={bidder}'>{bidder_name}</a>"
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

        # Comment in the discussion thread tagging the winner (if any)
        if bid >= rp and bidder:
            try:
                channel = await app.bot.get_chat(chan_id)
                discussion_id = getattr(channel, "linked_chat_id", None)
                if discussion_id:
                    await app.bot.send_message(
                        chat_id=discussion_id,
                        message_thread_id=post_id,
                        text=f"🏆 Winner: <a href='tg://user?id={bidder}'>{bidder_name}</a> with bid <b>{bid}</b>",
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
            except Exception:
                # Silently skip if no linked group or insufficient permissions
                pass