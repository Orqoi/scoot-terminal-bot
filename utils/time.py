import time
from datetime import datetime
from config.settings import SG_TZ

def now() -> int:
    return int(time.time())

def parse_end_time(duration_or_time: str) -> int:
    try:
        minutes = int(duration_or_time)
        return now() + minutes * 60
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(duration_or_time, fmt)
                return int(dt.replace(tzinfo=SG_TZ).timestamp())
            except ValueError:
                continue
        raise ValueError("Invalid datetime format. Use YYYY-MM-DD HH:MM[:SS] or minutes.")