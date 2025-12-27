from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.settings import logger, DEFAULT_CHANNEL_ID, SG_TZ
from controllers.check_auctions import check_auctions
from db.connection import DB
from datetime import datetime
from utils.time import now

async def publish_scheduled(app, a_id: int):
    row = DB.execute(
        """
        SELECT title, description, sb, rp, min_inc, end_time, anti_snipe, channel_id, photo_file_id
        FROM auctions
        WHERE auction_id = ? AND status = 'SCHEDULED'
        """,
        (a_id,),
    ).fetchone()
    if not row:
        return

    title, description, sb, rp, min_inc, end_time, anti, chan_id, photo_id = row
    caption = (
        f"🛒 <b>{title}</b>\n\n"
        f"{description}\n\n"
        f"💰 SB: {sb}\n"
        f"🏷 RP: {rp}\n"
        f"➕ Min Inc: {min_inc}\n"
        f"⏱ Ends: <b>{datetime.fromtimestamp(end_time, tz=SG_TZ).strftime('%Y-%m-%d %H:%M')}</b>\n"
        f"🛡 Anti-snipe: {anti} min\n\n"
        f"💬 Comment with a number to bid (or 'SB')"
    )
    sent = await app.bot.send_photo(chat_id=chan_id, photo=photo_id, caption=caption, parse_mode="HTML")
    DB.execute("UPDATE auctions SET channel_post_id = ?, status = 'LIVE' WHERE auction_id = ?", (sent.message_id, a_id))
    DB.commit()

async def on_startup(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_auctions, "interval", seconds=15, args=[app])
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    try:
        row = DB.execute("SELECT value FROM settings WHERE key = 'channel_id'").fetchone()
        if row:
            app.bot_data["channel_id"] = int(row[0])
            logger.info("Channel bound: %s", app.bot_data["channel_id"])
        elif DEFAULT_CHANNEL_ID:
            app.bot_data["channel_id"] = DEFAULT_CHANNEL_ID
            logger.info("Default CHANNEL_ID used: %s", DEFAULT_CHANNEL_ID)
        else:
            logger.info("No channel bound. Use /bind in private chat.")
    except Exception as e:
        logger.warning("Failed to load channel_id: %s", e)

    # Rehydrate scheduled auctions
    try:
        rows = DB.execute(
            "SELECT auction_id, start_time FROM auctions WHERE status = 'SCHEDULED'"
        ).fetchall()
        for a_id, start_ts in rows:
            run_dt = datetime.fromtimestamp(int(start_ts), tz=SG_TZ)
            if int(start_ts) > now():
                scheduler.add_job(
                    publish_scheduled,
                    "date",
                    run_date=run_dt,
                    args=[app, a_id],
                    id=f"publish_{a_id}",
                    replace_existing=True,
                )
            else:
                await publish_scheduled(app, a_id)
        logger.info("Rehydrated %d scheduled auctions", len(rows))
    except Exception as e:
        logger.warning("Failed to rehydrate scheduled auctions: %s", e)

    logger.info("Scheduler started")