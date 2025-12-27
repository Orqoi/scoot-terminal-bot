from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config.settings import logger
from controllers.check_auctions import check_auctions

async def on_startup(app):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_auctions, "interval", seconds=15, args=[app])
    scheduler.start()
    app.bot_data["scheduler"] = scheduler
    logger.info("Scheduler started")