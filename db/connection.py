import os
import sqlite3
from typing import Optional
from config.settings import logger

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def _connect(candidate: str, *, uri: bool = False) -> Optional[sqlite3.Connection]:
    try:
        if candidate != ":memory:" and not uri:
            dir_path = os.path.dirname(candidate)
            # Do not attempt to create persistent mount directories; they must be attached by the platform.
            if dir_path.startswith("/data"):
                if not (os.path.isdir(dir_path) and os.access(dir_path, os.W_OK | os.X_OK)):
                    logger.warning("DB directory not writable or missing: %s", dir_path)
                    raise PermissionError(f"DB directory not writable: {dir_path}")
            else:
                if dir_path and not os.path.exists(dir_path):
                    logger.debug("Creating DB directory: %s", dir_path)
                    os.makedirs(dir_path, exist_ok=True)
        return sqlite3.connect(candidate, check_same_thread=False, uri=uri)
    except Exception as e:
        logger.warning("DB connect failed for %s: %s", candidate, e)
        return None


def _init_db() -> sqlite3.Connection:
    env = os.environ.get("SQLITE_DB_PATH")
    logger.info("DB env: SQLITE_DB_PATH=%s", env)

    uri_candidate = None
    candidates = []

    if env:
        env = env.strip()
        lower = env.lower()
        if lower in (":memory:", "memory"):
            candidates.append(":memory:")
        elif env.startswith("file:"):
            uri_candidate = env
        else:
            # Resolve relative paths to project root (same root as bot.py)
            if not os.path.isabs(env):
                resolved = os.path.join(BASE_DIR, env)
                logger.info("Resolved relative DB path '%s' -> '%s'", env, resolved)
                candidates.append(resolved)
            else:
                candidates.append(env)
    else:
        # Default to project-local file for dev if no env provided
        candidates.append(os.path.join(BASE_DIR, "data", "auction.db"))

    logger.debug("DB candidate order: uri_candidate=%s candidates=%s", uri_candidate, candidates)

    db: Optional[sqlite3.Connection] = None
    chosen_path = uri_candidate or (candidates[0] if candidates else None)
    logger.info("DB connect: initial candidate=%s", chosen_path)

    if uri_candidate:
        db = _connect(uri_candidate, uri=True)
        chosen_path = uri_candidate

    idx = 0
    while db is None and idx < len(candidates):
        chosen_path = candidates[idx]
        logger.debug("DB connect attempt %d: %s", idx + 1, chosen_path)
        db = _connect(chosen_path)
        idx += 1

    if db is None:
        logger.error("DB connection failed after %d attempts", idx)
        raise RuntimeError("Failed to initialize sqlite database")
    else:
        logger.info("DB connection established")

    try:
        db.execute("PRAGMA journal_mode=WAL;")
        db.execute("PRAGMA foreign_keys=ON;")
        row = db.execute("PRAGMA database_list").fetchone()
        actual_path = row[2] if row else chosen_path
        logger.info("SQLite DB active path: %s", actual_path)
    except Exception as e:
        logger.warning("Failed to set PRAGMAs or log DB path: %s", e)

    try:
        cur = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='auctions'"
        )
        need_init = cur.fetchone() is None
        if need_init and os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                db.executescript(f.read())
            db.commit()
        elif need_init:
            raise RuntimeError(f"schema.sql not found at {SCHEMA_PATH}")
    except Exception as e:
        logger.error("Failed to apply schema: %s", e)
        raise

    # Ensure settings table exists even on already-initialized DBs
    try:
        db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        db.commit()
    except Exception as e:
        logger.error("Failed to ensure settings table: %s", e)

    # Create bindings table for per-user channel binding
    try:
        db.execute("CREATE TABLE IF NOT EXISTS bindings (user_id INTEGER PRIMARY KEY, channel_id INTEGER)")
        db.commit()
    except Exception as e:
        logger.error("Failed to ensure bindings table: %s", e)

    # Migration: add columns/indexes if missing
    try:
        cols = {row[1] for row in db.execute("PRAGMA table_info(auctions)").fetchall()}
        if "channel_id" not in cols:
            db.execute("ALTER TABLE auctions ADD COLUMN channel_id INTEGER")
            bound = db.execute("SELECT value FROM settings WHERE key = 'channel_id'").fetchone()
            if bound and bound[0].strip():
                try:
                    db.execute("UPDATE auctions SET channel_id = ?", (int(bound[0]),))
                except Exception:
                    pass
            db.commit()
        if "owner_user_id" not in cols:
            db.execute("ALTER TABLE auctions ADD COLUMN owner_user_id INTEGER")
            db.commit()
        if "start_time" not in cols:
            db.execute("ALTER TABLE auctions ADD COLUMN start_time INTEGER")
            db.commit()
        if "photo_file_id" not in cols:
            db.execute("ALTER TABLE auctions ADD COLUMN photo_file_id TEXT")
            db.commit()
        # Single-column reply anchor "chat_id:message_id"
        if "reply_anchor" not in cols:
            db.execute("ALTER TABLE auctions ADD COLUMN reply_anchor TEXT")
            db.commit()
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS auctions_channel_message_unique ON auctions(channel_id, channel_post_id)")
        db.commit()
    except Exception as e:
        logger.warning("Schema migration adjustments failed: %s", e)

    # Migration: remove column-level UNIQUE on channel_post_id by table recreation
    try:
        ddl_row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='auctions'").fetchone()
        ddl_sql = ddl_row[0] if ddl_row else ""
        if "channel_post_id INTEGER UNIQUE" in ddl_sql:
            logger.info("Migrating auctions schema to remove column-level UNIQUE on channel_post_id")
            db.execute("""
                CREATE TABLE IF NOT EXISTS auctions_mig (
                    auction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_post_id INTEGER,
                    channel_id INTEGER,
                    sb INTEGER,
                    rp INTEGER,
                    min_inc INTEGER,
                    end_time INTEGER,
                    anti_snipe INTEGER,
                    highest_bid INTEGER,
                    highest_bidder INTEGER,
                    status TEXT,
                    description TEXT,
                    title TEXT,
                    start_time INTEGER,
                    photo_file_id TEXT,
                    owner_user_id INTEGER
                )
            """)
            db.execute("""
                INSERT INTO auctions_mig (
                    auction_id, channel_post_id, channel_id, sb, rp, min_inc, end_time, anti_snipe,
                    highest_bid, highest_bidder, status, description, title, start_time, photo_file_id, owner_user_id
                )
                SELECT auction_id, channel_post_id, channel_id, sb, rp, min_inc, end_time, anti_snipe,
                       highest_bid, highest_bidder, status, description, title, start_time, photo_file_id, owner_user_id
                FROM auctions
            """)
            db.execute("DROP TABLE auctions")
            db.execute("ALTER TABLE auctions_mig RENAME TO auctions")
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS auctions_channel_message_unique ON auctions(channel_id, channel_post_id)")
            db.commit()
    except Exception as e:
        logger.warning("Unique constraint migration failed: %s", e)

    return db


DB = _init_db()