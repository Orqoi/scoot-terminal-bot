import os
import sqlite3
from typing import Optional
from config.settings import logger

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
SCHEMA_PATH = os.path.join(BASE_DIR, "schema.sql")


def _connect(candidate: str, *, uri: bool = False) -> Optional[sqlite3.Connection]:
    try:
        if candidate != ":memory:" and not uri:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
        return sqlite3.connect(candidate, check_same_thread=False, uri=uri)
    except Exception as e:
        logger.warning("DB connect failed for %s: %s", candidate, e)
        return None


def _init_db() -> sqlite3.Connection:
    env = (
        os.environ.get("SQLITE_DB_PATH")
        or os.environ.get("DB_PATH")
        or os.environ.get("DATABASE_URL")
    )

    uri_candidate = None
    candidates = []

    if env:
        env = env.strip()
        lower = env.lower()
        if lower in (":memory:", "memory"):
            candidates.append(":memory:")
        elif env.startswith("file:"):
            uri_candidate = env
        elif env.startswith("sqlite:///"):
            candidates.append(env[len("sqlite:///") :])
        elif env.startswith("sqlite://"):
            candidates.append(env[len("sqlite://") :])
        else:
            candidates.append(env)

    candidates.extend(
        [
            os.path.join(BASE_DIR, "data", "auction.db"),
            "/tmp/auction.db",
            ":memory:",
        ]
    )

    db: Optional[sqlite3.Connection] = None
    if uri_candidate:
        db = _connect(uri_candidate, uri=True)

    idx = 0
    while db is None and idx < len(candidates):
        db = _connect(candidates[idx])
        idx += 1

    if db is None:
        raise RuntimeError("Failed to initialize sqlite database")

    try:
        db.execute("PRAGMA journal_mode=WAL;")
        db.execute("PRAGMA foreign_keys=ON;")
    except Exception as e:
        logger.warning("Failed to set PRAGMAs: %s", e)

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

        # Add channel_id if missing (existing migration)
        if "channel_id" not in cols:
            db.execute("ALTER TABLE auctions ADD COLUMN channel_id INTEGER")
            bound = db.execute("SELECT value FROM settings WHERE key = 'channel_id'").fetchone()
            if bound and bound[0].strip():
                try:
                    db.execute("UPDATE auctions SET channel_id = ?", (int(bound[0]),))
                except Exception:
                    pass
            db.commit()

        # Add owner_user_id for per-auction ownership
        if "owner_user_id" not in cols:
            db.execute("ALTER TABLE auctions ADD COLUMN owner_user_id INTEGER")
            db.commit()

        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS auctions_channel_message_unique ON auctions(channel_id, channel_post_id)")
        db.commit()
    except Exception as e:
        logger.warning("Schema migration adjustments failed: %s", e)

    return db


DB = _init_db()