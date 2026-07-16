"""SQLite schema for Market Agent — v3 SaaS Multi-User."""

# ── Core tables ────────────────────────────────────────────────────────────────

CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    -- Access control
    is_active INTEGER DEFAULT 1,        -- 0 = banned
    is_admin INTEGER DEFAULT 0,         -- 1 = owner/admin
    -- Subscription
    plan TEXT DEFAULT 'free',           -- 'free' | 'pro' | 'unlimited'
    plan_expires_at TEXT,               -- NULL = never expires
    -- Onboarding
    onboarded INTEGER DEFAULT 0,        -- 1 = completed setup wizard
    created_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT DEFAULT (datetime('now'))
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
    condition TEXT DEFAULT 'any',
    purpose TEXT DEFAULT 'self',
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
    published_at TEXT,
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
    -- AI fields (nullable)
    ai_score REAL,
    ai_explanation TEXT,
    ai_why_good TEXT,
    ai_risks TEXT,
    ai_provider TEXT,
    confidence REAL DEFAULT 0.5,
    market_liquidity TEXT DEFAULT 'medium',
    analyzed_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_OPPORTUNITIES = """
CREATE TABLE IF NOT EXISTS opportunities (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title TEXT NOT NULL,
    category TEXT,
    best_price REAL,
    avg_price REAL,
    median_price REAL,
    deal_score REAL,
    confidence REAL,
    market_liquidity TEXT,
    recommendation TEXT,
    url TEXT,
    listings_count INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
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

# ── User Settings (full per-user config) ───────────────────────────────────────

CREATE_USER_SETTINGS = """
CREATE TABLE IF NOT EXISTS user_settings (
    id INTEGER PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES users(id),

    -- Location / Sources
    city TEXT DEFAULT '',               -- default city for searches
    sources_avito INTEGER DEFAULT 1,    -- 1 = enabled
    sources_youla INTEGER DEFAULT 1,

    -- Collector
    collector_interval_sec INTEGER DEFAULT 300,

    -- Deal thresholds
    threshold_buy REAL DEFAULT 70.0,    -- score >= this → 🔥 BUY alert
    threshold_maybe REAL DEFAULT 50.0,  -- score >= this → maybe alert

    -- Hunter Mode
    hunter_enabled INTEGER DEFAULT 0,
    hunter_interval_sec INTEGER DEFAULT 300,
    hunter_min_savings_pct REAL DEFAULT 10.0,
    hunter_min_score REAL DEFAULT 50.0,

    -- AI
    ai_provider TEXT DEFAULT '',        -- 'wormsoft' | 'openai' | 'gemini' | 'anthropic' | ''
    ai_api_key TEXT DEFAULT '',
    ai_model TEXT DEFAULT '',

    -- Notifications
    notifications_enabled INTEGER DEFAULT 1,
    notify_on_buy INTEGER DEFAULT 1,
    notify_on_maybe INTEGER DEFAULT 0,
    notify_quiet_hours_start INTEGER DEFAULT 23,  -- hour 0-23
    notify_quiet_hours_end INTEGER DEFAULT 8,

    updated_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_SAVED_FINDS = """
CREATE TABLE IF NOT EXISTS saved_finds (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    listing_id INTEGER REFERENCES listings(id),
    analysis_id INTEGER REFERENCES analysis(id),
    note TEXT,
    saved_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, listing_id)
);
"""

CREATE_MARKET_RADAR = """
CREATE TABLE IF NOT EXISTS market_radar (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    category TEXT NOT NULL,
    avg_price REAL DEFAULT 0,
    median_price REAL DEFAULT 0,
    sample_size INTEGER DEFAULT 0,
    trend TEXT DEFAULT 'stable',
    trend_pct REAL DEFAULT 0,
    trend_emoji TEXT DEFAULT '→',
    ai_comment TEXT DEFAULT '',
    hot_deals_count INTEGER DEFAULT 0,
    snapshot_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_AI_CACHE = """
CREATE TABLE IF NOT EXISTS ai_cache (
    id INTEGER PRIMARY KEY,
    cache_key TEXT UNIQUE NOT NULL,
    provider TEXT NOT NULL,
    response TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

CREATE_BROADCASTS = """
CREATE TABLE IF NOT EXISTS broadcasts (
    id INTEGER PRIMARY KEY,
    admin_id INTEGER REFERENCES users(id),
    message TEXT NOT NULL,
    sent_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

# ── Indexes ────────────────────────────────────────────────────────────────────

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_listings_source ON listings(source);",
    "CREATE INDEX IF NOT EXISTS idx_listings_url ON listings(url);",
    "CREATE INDEX IF NOT EXISTS idx_listings_price ON listings(price);",
    "CREATE INDEX IF NOT EXISTS idx_listings_parsed ON listings(parsed_at);",
    "CREATE INDEX IF NOT EXISTS idx_analysis_score ON analysis(deal_score);",
    "CREATE INDEX IF NOT EXISTS idx_analysis_search ON analysis(search_id);",
    "CREATE INDEX IF NOT EXISTS idx_searches_user ON searches(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_user ON alerts(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_alerts_sent ON alerts(sent_at);",
    "CREATE INDEX IF NOT EXISTS idx_saved_user ON saved_finds(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_radar_user ON market_radar(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_ai_cache_key ON ai_cache(cache_key);",
    "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active);",
]

# ── Migration: add new columns to existing DB ──────────────────────────────────

MIGRATIONS = [
    # v2 → v3: add new user fields
    "ALTER TABLE users ADD COLUMN first_name TEXT;",
    "ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1;",
    "ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0;",
    "ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free';",
    "ALTER TABLE users ADD COLUMN plan_expires_at TEXT;",
    "ALTER TABLE users ADD COLUMN onboarded INTEGER DEFAULT 0;",
    "ALTER TABLE users ADD COLUMN last_seen_at TEXT DEFAULT (datetime('now'));",
    # v2 → v3: add new user_settings fields
    "ALTER TABLE user_settings ADD COLUMN city TEXT DEFAULT '';",
    "ALTER TABLE user_settings ADD COLUMN sources_avito INTEGER DEFAULT 1;",
    "ALTER TABLE user_settings ADD COLUMN sources_youla INTEGER DEFAULT 1;",
    "ALTER TABLE user_settings ADD COLUMN collector_interval_sec INTEGER DEFAULT 300;",
    "ALTER TABLE user_settings ADD COLUMN threshold_buy REAL DEFAULT 70.0;",
    "ALTER TABLE user_settings ADD COLUMN threshold_maybe REAL DEFAULT 50.0;",
    "ALTER TABLE user_settings ADD COLUMN notify_quiet_hours_start INTEGER DEFAULT 23;",
    "ALTER TABLE user_settings ADD COLUMN notify_quiet_hours_end INTEGER DEFAULT 8;",
    # add published_at to listings
    "ALTER TABLE listings ADD COLUMN published_at TEXT;",
    # add confidence & market_liquidity to analysis
    "ALTER TABLE analysis ADD COLUMN confidence REAL DEFAULT 0.5;",
    "ALTER TABLE analysis ADD COLUMN market_liquidity TEXT DEFAULT 'medium';",
    # add opportunity_id to listings
    "ALTER TABLE listings ADD COLUMN opportunity_id INTEGER REFERENCES opportunities(id);",
]

SCHEMA = [
    CREATE_USERS,
    CREATE_SEARCHES,
    CREATE_LISTINGS,
    CREATE_OPPORTUNITIES,
    CREATE_ANALYSIS,
    CREATE_ALERTS,
    CREATE_USER_SETTINGS,
    CREATE_SAVED_FINDS,
    CREATE_MARKET_RADAR,
    CREATE_AI_CACHE,
    CREATE_BROADCASTS,
    *CREATE_INDEXES,
]
