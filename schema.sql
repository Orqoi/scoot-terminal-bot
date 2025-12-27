CREATE TABLE IF NOT EXISTS auctions (
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
);
-- Ensure config storage for binding
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS bindings (
    user_id INTEGER PRIMARY KEY,
    channel_id INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS auctions_channel_message_unique ON auctions(channel_id, channel_post_id);
