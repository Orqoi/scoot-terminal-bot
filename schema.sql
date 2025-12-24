CREATE TABLE IF NOT EXISTS auctions (
    auction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_post_id INTEGER UNIQUE,
    sb INTEGER,
    rp INTEGER,
    min_inc INTEGER,
    end_time INTEGER,
    anti_snipe INTEGER,
    highest_bid INTEGER,
    highest_bidder INTEGER,
    status TEXT,
    description TEXT
);
