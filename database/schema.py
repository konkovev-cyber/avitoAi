"""SQLite schema for Market Agent."""

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_SEARCHES = """
CREATE TABLE IF NOT EXISTS searches (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    query TEXT NOT NULL,
    category TEXT,
    keywords TEXT,
    max_price REAL,
    min_price REAL,
    location TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_LISTINGS = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT,
    title TEXT NOT NULL,
    description TEXT,
    price REAL NOT NULL,
    currency TEXT DEFAULT 'RUB',
    location TEXT,
    seller_name TEXT,
    seller_rating REAL,
    seller_deals_count INTEGER,
    seller_registered_at TEXT,
    url TEXT UNIQUE NOT NULL,
    images TEXT,
    hash TEXT,
    parsed_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_ANALYSIS = """
CREATE TABLE IF NOT EXISTS analysis (
    id INTEGER PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id),
    search_id INTEGER REFERENCES searches(id),
    market_price REAL,
    market_price_min REAL,
    market_price_max REAL,
    price_delta_pct REAL,
    deal_score REAL,
    risk_score REAL,
    risk_factors TEXT,
    recommendation TEXT,
    analyzed_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_ALERTS = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    analysis_id INTEGER REFERENCES analysis(id),
    sent_at TEXT DEFAULT (datetime('now'))
);
"""

# Indexes
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);",
    "CREATE INDEX IF NOT EXISTS idx_listings_url ON listings(url);",
    "CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);",
    "CREATE INDEX IF NOT EXISTS idx_analysis_score ON analysis(deal_score);",
    "CREATE INDEX IF NOT EXISTS idx_analysis_search ON analysis(search_id);",
    "CREATE INDEX IF NOT EXISTS idx_searches_user ON searches(user_id);",
]

SCHEMA = [
    CREATE_USERS,
    CREATE_SEARCHES,
    CREATE_LISTINGS,
    CREATE_ANALYSIS,
    CREATE_ALERTS,
    *CREATE_INDEXES,
]
