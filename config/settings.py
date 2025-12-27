import os
import logging
from dotenv import load_dotenv
from datetime import timezone, timedelta

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
BIND_SECRET = os.environ.get("BIND_SECRET")
DEFAULT_CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable not set")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("auction-bot")

SG_TZ = timezone(timedelta(hours=8))