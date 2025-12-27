from telegram.ext import Application
from config.settings import CHANNEL_ID
from db.connection import DB
from utils.time import now

async def check_auctions(app: Application):
    rows = DB.execute(
        """
        SELECT auction_id, channel_post_id, title, rp, highest_bid, highest_bidder, description
        FROM auctions
        WHERE status = 'LIVE' AND end_time <= ?
        """,
        (now(),),
    ).fetchall()

    for auction_id, post_id, title, rp, bid, bidder, description in rows:
        DB.execute(
            "UPDATE auctions SET status = 'ENDED' WHERE auction_id = ?",
            (auction_id,),
        )
        DB.commit()

        if bid >= rp and bidder:
            user = await app.bot.get_chat(bidder)
            bidder_name = user.first_name or "User"
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
            chat_id=CHANNEL_ID,
            message_id=post_id,
            caption=caption,
            parse_mode="HTML",
        )