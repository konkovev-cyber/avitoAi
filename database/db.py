"""Database operations for Market Agent."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import settings
from models import RawListing, SearchQuery, DealScore
from .schema import SCHEMA

log = logging.getLogger("market_agent.db")


class Database:
    """SQLite database wrapper with WAL mode."""

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

    def init_schema(self):
        conn = self.connect()
        for stmt in SCHEMA:
            conn.execute(stmt)
        conn.commit()
        log.info("Database schema initialized at %s", self.db_path)

    # ── Users ────────────────────────────────────────

    def upsert_user(self, telegram_id: int, username: Optional[str] = None) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO users (telegram_id, username) VALUES (?, ?) "
            "ON CONFLICT(telegram_id) DO UPDATE SET username=COALESCE(?, username)",
            (telegram_id, username, username),
        )
        conn.commit()
        return cur.lastrowid or self.get_user_by_telegram(telegram_id)

    def get_user_by_telegram(self, telegram_id: int) -> Optional[dict]:
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── Searches ─────────────────────────────────────

    def create_search(self, search: SearchQuery) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO searches (user_id, query, category, keywords, max_price, min_price, location) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                search.user_id,
                search.query,
                search.category,
                json.dumps(search.keywords),
                search.max_price,
                search.min_price,
                search.location,
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

    def deactivate_search(self, search_id: int):
        conn = self.connect()
        conn.execute("UPDATE searches SET active = 0 WHERE id = ?", (search_id,))
        conn.commit()

    # ── Listings ─────────────────────────────────────

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
        """Get similar listings for market price estimation."""
        conn = self.connect()
        rows = conn.execute(
            """SELECT * FROM listings
            WHERE price > 0 AND price <= ?
            ORDER BY parsed_at DESC LIMIT ?""",
            (max_price * 1.5, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_alerts(self, user_id: int, limit: int = 10) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            """SELECT a.*, l.title, l.price, l.url, l.source,
                      an.deal_score, an.recommendation, an.price_delta_pct
            FROM alerts a
            JOIN analysis an ON a.analysis_id = an.id
            JOIN listings l ON an.listing_id = l.id
            WHERE a.user_id = ?
            ORDER BY a.sent_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Analysis ─────────────────────────────────────

    def save_analysis(self, listing_id: int, search_id: int, deal: DealScore) -> int:
        conn = self.connect()
        cur = conn.execute(
            """INSERT INTO analysis
            (listing_id, search_id, market_price, price_delta_pct,
             deal_score, risk_score, risk_factors, recommendation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                listing_id,
                search_id,
                deal.market_price,
                deal.price_delta_pct,
                deal.score,
                deal.risk_score,
                json.dumps(deal.risk_factors),
                deal.recommendation,
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

    # ── Stats ────────────────────────────────────────

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

    @staticmethod
    def _hash_listing(listing: RawListing) -> str:
        import hashlib
        raw = f"{listing.source}|{listing.title}|{listing.price}|{listing.seller_name}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
