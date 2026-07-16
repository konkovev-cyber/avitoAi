"""SQLite database implementation for Market Agent."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings
from models import RawListing, SearchQuery, DealScore, MarketRadarSnapshot
from database.base import BaseDatabase
from .schema import SCHEMA, MIGRATIONS

log = logging.getLogger("market_agent.db.sqlite")


class SQLiteDatabase(BaseDatabase):
    """SQLite implementation of the BaseDatabase with WAL mode."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        return self._conn

    def init_schema(self) -> None:
        conn = self.connect()
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()
        self._run_migrations()
        log.info("SQLite database schema initialized at %s", self.db_path)

    def _run_migrations(self) -> None:
        """Apply ALTER TABLE migrations — silently skip if column already exists."""
        conn = self.connect()
        for sql in MIGRATIONS:
            try:
                conn.execute(sql)
                conn.commit()
            except Exception:
                pass  # column already exists or other harmless error

    # ── Users ────────────────────────────────────────────────────────────────

    def upsert_user(self, telegram_id: int, username: Optional[str] = None,
                    first_name: Optional[str] = None) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO users (telegram_id, username, first_name) VALUES (?, ?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET "
            "username=COALESCE(?, username), "
            "first_name=COALESCE(?, first_name), "
            "last_seen_at=datetime('now')",
            (telegram_id, username, first_name, username, first_name),
        )
        conn.commit()
        return cur.lastrowid or self.get_user_by_telegram(telegram_id)["id"]

    def get_user_by_telegram(self, telegram_id: int) -> Optional[dict]:
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None

    def is_banned(self, telegram_id: int) -> bool:
        conn = self.connect()
        row = conn.execute(
            "SELECT is_active FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return bool(row and row["is_active"] == 0)

    def is_admin(self, telegram_id: int) -> bool:
        conn = self.connect()
        row = conn.execute(
            "SELECT is_admin FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return bool(row and row["is_admin"] == 1)

    def set_admin(self, telegram_id: int, is_admin: bool = True) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE users SET is_admin = ? WHERE telegram_id = ?",
            (1 if is_admin else 0, telegram_id),
        )
        conn.commit()

    def ban_user(self, telegram_id: int, banned: bool = True) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE users SET is_active = ? WHERE telegram_id = ?",
            (0 if banned else 1, telegram_id),
        )
        conn.commit()

    def set_plan(self, telegram_id: int, plan: str, expires_at: Optional[str] = None) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE users SET plan = ?, plan_expires_at = ? WHERE telegram_id = ?",
            (plan, expires_at, telegram_id),
        )
        conn.commit()

    def mark_onboarded(self, telegram_id: int) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE users SET onboarded = 1 WHERE telegram_id = ?", (telegram_id,)
        )
        conn.commit()

    def get_all_users(self, limit: int = 200) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_admin_stats(self) -> dict:
        conn = self.connect()
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0]
        today_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE date(created_at)=date('now')"
        ).fetchone()[0]
        pro_users = conn.execute(
            "SELECT COUNT(*) FROM users WHERE plan != 'free'"
        ).fetchone()[0]
        total_searches = conn.execute("SELECT COUNT(*) FROM searches WHERE active=1").fetchone()[0]
        today_alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE date(sent_at)=date('now')"
        ).fetchone()[0]
        total_listings = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        return {
            "total_users": total_users,
            "active_users": active_users,
            "today_new_users": today_users,
            "pro_users": pro_users,
            "active_searches": total_searches,
            "today_alerts": today_alerts,
            "total_listings": total_listings,
        }

    # ── Searches ─────────────────────────────────────────────────────────────

    def create_search(self, search: SearchQuery) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO searches "
            "(user_id, query, category, keywords, max_price, min_price, location, condition, purpose) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                search.user_id,
                search.query,
                search.category,
                json.dumps(search.keywords),
                search.max_price,
                search.min_price,
                search.location,
                search.condition,
                search.purpose,
            ),
        )
        conn.commit()
        return cur.lastrowid

    def get_active_searches(self) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM searches WHERE active = 1 ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_user_searches(self, user_id: int) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM searches WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def deactivate_search(self, search_id: int) -> None:
        conn = self.connect()
        conn.execute("UPDATE searches SET active = 0 WHERE id = ?", (search_id,))
        conn.commit()

    def activate_search(self, search_id: int) -> None:
        conn = self.connect()
        conn.execute("UPDATE searches SET active = 1 WHERE id = ?", (search_id,))
        conn.commit()

    def get_search_stats(self, search_id: int) -> dict:
        conn = self.connect()
        total = conn.execute(
            "SELECT COUNT(*) FROM analysis WHERE search_id = ?", (search_id,)
        ).fetchone()[0]
        good = conn.execute(
            "SELECT COUNT(*) FROM analysis WHERE search_id = ? AND deal_score >= 70",
            (search_id,),
        ).fetchone()[0]
        return {"total": total, "good_deals": good}

    # ── Listings ─────────────────────────────────────────────────────────────

    def insert_listing(self, listing: RawListing) -> int:
        conn = self.connect()
        try:
            cur = conn.execute(
                """INSERT OR IGNORE INTO listings
                (source, source_id, title, description, price, currency, location,
                 seller_name, seller_rating, seller_deals_count, seller_registered_at,
                 url, images, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    listing.source,
                    listing.source_id,
                    listing.title[:500],
                    listing.description[:5000] if listing.description else None,
                    listing.price,
                    listing.currency,
                    listing.location,
                    listing.seller_name,
                    listing.seller_rating,
                    listing.seller_deals_count,
                    listing.seller_registered_at,
                    listing.url,
                    json.dumps(listing.images),
                    self._hash_listing(listing),
                ),
            )
            conn.commit()
            return cur.lastrowid or 0
        except Exception as e:
            log.warning("Failed to insert listing %s: %s", listing.url[:80], e)
            return 0

    def listing_exists(self, url: str) -> bool:
        conn = self.connect()
        row = conn.execute(
            "SELECT 1 FROM listings WHERE url = ?", (url,)
        ).fetchone()
        return row is not None

    def get_listings_for_price_analysis(
        self, category: str, max_price: float, limit: int = 100
    ) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM listings
            WHERE price > 0 AND price <= ?
            ORDER BY parsed_at DESC LIMIT ?""",
            (max_price * 1.5, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Analysis ─────────────────────────────────────────────────────────────

    def save_analysis(self, listing_id: int, search_id: int, deal: DealScore) -> int:
        conn = self.connect()
        cur = conn.execute(
            """INSERT INTO analysis
            (listing_id, search_id, market_price, price_delta_pct,
             deal_score, risk_score, risk_factors, recommendation,
             ai_score, ai_explanation, ai_why_good, ai_risks, ai_provider,
             confidence, market_liquidity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing_id,
                search_id,
                deal.market_price,
                deal.price_delta_pct,
                deal.score,
                deal.risk_score,
                json.dumps(deal.risk_factors),
                deal.recommendation,
                deal.ai_score,
                deal.ai_explanation,
                json.dumps(deal.ai_why_good) if deal.ai_why_good else None,
                json.dumps(deal.ai_risks) if deal.ai_risks else None,
                deal.ai_provider,
                deal.confidence,
                deal.market_liquidity,
            ),
        )
        conn.commit()
        return cur.lastrowid

    def save_alert(self, user_id: int, analysis_id: int) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO alerts (user_id, analysis_id) VALUES (?, ?)",
            (user_id, analysis_id),
        )
        conn.commit()
        return cur.lastrowid

    def get_recent_alerts(self, user_id: int, limit: int = 10) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT a.*, l.title, l.price, l.url, l.source, l.description,
                      l.seller_name, l.seller_rating, l.images,
                      an.deal_score, an.recommendation, an.price_delta_pct,
                      an.market_price, an.risk_score, an.risk_factors,
                      an.ai_score, an.ai_explanation, an.ai_why_good,
                      an.ai_risks, an.ai_provider, an.confidence,
                      an.market_liquidity, an.id as analysis_id
            FROM alerts a
            JOIN analysis an ON a.analysis_id = an.id
            JOIN listings l ON an.listing_id = l.id
            WHERE a.user_id = ?
            ORDER BY a.sent_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for field in ("risk_factors", "ai_why_good", "ai_risks", "images"):
                if d.get(field) and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except Exception:
                        d[field] = []
            result.append(d)
        return result

    # ── Opportunities ─────────────────────────────────────────────────────────

    def create_opportunity(self, opportunity: dict) -> int:
        conn = self.connect()
        cur = conn.execute(
            """INSERT INTO opportunities
            (user_id, title, category, best_price, avg_price, median_price,
             deal_score, confidence, market_liquidity, recommendation, url, listings_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                opportunity.get("user_id"),
                opportunity.get("title"),
                opportunity.get("category"),
                opportunity.get("best_price"),
                opportunity.get("avg_price"),
                opportunity.get("median_price"),
                opportunity.get("deal_score"),
                opportunity.get("confidence"),
                opportunity.get("market_liquidity"),
                opportunity.get("recommendation"),
                opportunity.get("url"),
                opportunity.get("listings_count", 1),
            ),
        )
        conn.commit()
        return cur.lastrowid

    def update_opportunity(self, opp_id: int, **kwargs) -> None:
        conn = self.connect()
        allowed = {
            "title", "category", "best_price", "avg_price", "median_price",
            "deal_score", "confidence", "market_liquidity", "recommendation", "url", "listings_count"
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [opp_id]
        conn.execute(
            f"UPDATE opportunities SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        conn.commit()

    def get_opportunity(self, opp_id: int) -> Optional[dict]:
        conn = self.connect()
        row = conn.execute("SELECT * FROM opportunities WHERE id = ?", (opp_id,)).fetchone()
        return dict(row) if row else None

    def get_user_opportunities(self, user_id: int, limit: int = 50) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM opportunities WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def find_matching_opportunity(self, user_id: int, title: str, price: float) -> Optional[dict]:
        conn = self.connect()
        words = [w for w in title.lower().split() if len(w) > 3]
        if not words:
            return None
        like_pattern = f"%{words[0]}%"
        rows = conn.execute(
            """SELECT * FROM opportunities
            WHERE user_id = ? AND title LIKE ?
            AND best_price >= ? AND best_price <= ?
            ORDER BY updated_at DESC""",
            (user_id, like_pattern, price * 0.7, price * 1.3),
        ).fetchall()
        for row in rows:
            opp_title = row["title"].lower()
            matches = sum(1 for w in words if w in opp_title)
            if matches >= min(2, len(words)):
                return dict(row)
        return None

    def link_listing_to_opportunity(self, listing_id: int, opp_id: int) -> None:
        conn = self.connect()
        conn.execute("UPDATE listings SET opportunity_id = ? WHERE id = ?", (opp_id, listing_id))
        conn.commit()

    # ── User Settings ─────────────────────────────────────────────────────────

    def get_user_settings_by_search_id(self, search_id: int) -> dict:
        conn = self.connect()
        row = conn.execute(
            "SELECT user_id FROM searches WHERE id = ?", (search_id,)
        ).fetchone()
        if not row:
            return self.get_user_settings(0)
        return self.get_user_settings(row["user_id"])

    def get_user_settings(self, user_id: int) -> dict:
        """user_id = internal users.id."""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM user_settings WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "user_id": user_id,
            "city": "",
            "sources_avito": 1,
            "sources_youla": 1,
            "collector_interval_sec": 300,
            "threshold_buy": 70.0,
            "threshold_maybe": 50.0,
            "hunter_enabled": 0,
            "hunter_interval_sec": 300,
            "hunter_min_savings_pct": 10.0,
            "hunter_min_score": 50.0,
            "ai_provider": "",
            "ai_api_key": "",
            "ai_model": "",
            "notifications_enabled": 1,
            "notify_on_buy": 1,
            "notify_on_maybe": 0,
            "notify_quiet_hours_start": 23,
            "notify_quiet_hours_end": 8,
        }

    def get_user_settings_by_tg(self, telegram_id: int) -> dict:
        """Convenience: accepts telegram_id, looks up internal user_id."""
        row = self.get_user_by_telegram(telegram_id)
        if not row:
            return {"user_id": 0, "city": ""}
        return self.get_user_settings(row["id"])

    def upsert_user_settings(self, user_id: int, **kwargs) -> None:
        """user_id = users.id (internal ID, NOT telegram_id)."""
        conn = self.connect()
        allowed = {
            "city", "sources_avito", "sources_youla",
            "collector_interval_sec", "threshold_buy", "threshold_maybe",
            "hunter_enabled", "hunter_interval_sec",
            "hunter_min_savings_pct", "hunter_min_score",
            "ai_provider", "ai_api_key", "ai_model",
            "notifications_enabled", "notify_on_buy", "notify_on_maybe",
            "notify_quiet_hours_start", "notify_quiet_hours_end",
        }
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return
        conn.execute(
            "INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,)
        )
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        conn.execute(
            f"UPDATE user_settings SET {set_clause}, updated_at = datetime('now') "
            f"WHERE user_id = ?",
            values,
        )
        conn.commit()

    def upsert_user_settings_by_tg(self, telegram_id: int, **kwargs) -> None:
        """Convenience: accepts telegram_id, looks up internal user_id."""
        row = self.get_user_by_telegram(telegram_id)
        if row:
            self.upsert_user_settings(row["id"], **kwargs)

    def get_internal_user_id(self, telegram_id: int) -> int:
        """Convert telegram_id to internal users.id."""
        row = self.get_user_by_telegram(telegram_id)
        return row["id"] if row else 0

    # ── Saved Finds ───────────────────────────────────────────────────────────

    def save_find(self, user_id: int, listing_id: int, analysis_id: int, note: str = "") -> bool:
        conn = self.connect()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO saved_finds (user_id, listing_id, analysis_id, note) "
                "VALUES (?, ?, ?, ?)",
                (user_id, listing_id, analysis_id, note),
            )
            conn.commit()
            return True
        except Exception as e:
            log.warning("Failed to save find: %s", e)
            return False

    def get_saved_finds(self, user_id: int, limit: int = 20) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT sf.*, l.title, l.price, l.url, l.source,
                      an.deal_score, an.recommendation, an.price_delta_pct,
                      an.market_price, an.ai_explanation
            FROM saved_finds sf
            JOIN listings l ON sf.listing_id = l.id
            JOIN analysis an ON sf.analysis_id = an.id
            WHERE sf.user_id = ?
            ORDER BY sf.saved_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def remove_saved_find(self, user_id: int, listing_id: int) -> None:
        conn = self.connect()
        conn.execute(
            "DELETE FROM saved_finds WHERE user_id = ? AND listing_id = ?",
            (user_id, listing_id),
        )
        conn.commit()

    # ── Market Radar ──────────────────────────────────────────────────────────

    def save_market_radar(self, user_id: int, snapshot: MarketRadarSnapshot) -> None:
        conn = self.connect()
        conn.execute(
            """INSERT INTO market_radar
            (user_id, category, avg_price, median_price, sample_size,
             trend, trend_pct, trend_emoji, ai_comment, hot_deals_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id,
                snapshot.category,
                snapshot.avg_price,
                snapshot.median_price,
                snapshot.sample_size,
                snapshot.trend,
                snapshot.trend_pct,
                snapshot.trend_emoji,
                snapshot.ai_comment,
                snapshot.hot_deals_count,
            ),
        )
        conn.commit()

    def get_latest_radar(self, user_id: int, limit: int = 5) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM market_radar
            WHERE user_id = ?
            GROUP BY category
            HAVING MAX(snapshot_at)
            ORDER BY hot_deals_count DESC, ABS(trend_pct) DESC
            LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── AI Cache ─────────────────────────────────────────────────────────────

    def get_ai_cache(self, cache_key: str) -> Optional[str]:
        conn = self.connect()
        row = conn.execute(
            "SELECT response FROM ai_cache WHERE cache_key = ? "
            "AND created_at > datetime('now', '-24 hours')",
            (cache_key,),
        ).fetchone()
        return row["response"] if row else None

    def set_ai_cache(self, cache_key: str, provider: str, response: str) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT OR REPLACE INTO ai_cache (cache_key, provider, response) VALUES (?, ?, ?)",
            (cache_key, provider, response),
        )
        conn.commit()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        conn = self.connect()
        total_listings = conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
        total_analyses = conn.execute("SELECT COUNT(*) FROM analysis").fetchone()[0]
        total_alerts = conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0]
        by_source = conn.execute(
            "SELECT source, COUNT(*) FROM listings GROUP BY source"
        ).fetchall()
        return {
            "listings": total_listings,
            "analyses": total_analyses,
            "alerts": total_alerts,
            "by_source": {r[0]: r[1] for r in by_source},
        }

    def get_user_stats(self, user_id: int) -> dict:
        conn = self.connect()
        active = conn.execute(
            "SELECT COUNT(*) FROM searches WHERE user_id = ? AND active = 1",
            (user_id,),
        ).fetchone()[0]
        total_alerts = conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        good = conn.execute(
            """SELECT COUNT(*) FROM alerts a
            JOIN analysis an ON a.analysis_id = an.id
            WHERE a.user_id = ? AND an.deal_score >= 70""",
            (user_id,),
        ).fetchone()[0]
        avg_raw = conn.execute(
            """SELECT AVG(ABS(an.price_delta_pct))
            FROM alerts a
            JOIN analysis an ON a.analysis_id = an.id
            WHERE a.user_id = ? AND an.price_delta_pct < 0""",
            (user_id,),
        ).fetchone()[0] or 0
        saved = conn.execute(
            "SELECT COUNT(*) FROM saved_finds WHERE user_id = ?", (user_id,)
        ).fetchone()[0]
        today_checked = conn.execute(
            """SELECT COUNT(*) FROM alerts a
            JOIN analysis an ON a.analysis_id = an.id
            WHERE a.user_id = ? AND date(a.sent_at) = date('now')""",
            (user_id,),
        ).fetchone()[0]
        today_good = conn.execute(
            """SELECT COUNT(*) FROM alerts a
            JOIN analysis an ON a.analysis_id = an.id
            WHERE a.user_id = ? AND date(a.sent_at) = date('now') AND an.deal_score >= 70""",
            (user_id,),
        ).fetchone()[0]
        return {
            "active_searches": active,
            "total_alerts": total_alerts,
            "good_deals": good,
            "avg_savings": round(abs(avg_raw), 1),
            "saved_finds": saved,
            "today_checked": today_checked,
            "today_good": today_good,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _hash_listing(listing: RawListing) -> str:
        raw = f"{listing.source}|{listing.title}|{listing.price}|{listing.seller_name}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
