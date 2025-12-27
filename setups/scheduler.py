from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.settings import logger, DEFAULT_CHANNEL_ID
from controllers.check_auctions import check_auctions
from db.connection import DB

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

    logger.info("Scheduler started")