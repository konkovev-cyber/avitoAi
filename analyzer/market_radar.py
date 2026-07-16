"""Market Radar — aggregates category trends and generates AI market intelligence.

The Radar runs hourly (or on demand) and provides a CEO Dashboard view:
- Price trends per category (up/down/stable)
- Hot deals count
- AI comments on each category
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from ai.base import AIProvider, MarketRadarItem
from database.db import Database
from models import MarketRadarSnapshot

log = logging.getLogger("market_agent.analyzer.market_radar")


class MarketRadar:
    """Builds Market Radar snapshots from listing data."""

    def __init__(self, db: Database, ai_provider: Optional[AIProvider] = None):
        self.db = db
        self.ai = ai_provider

    def _get_category_data(self, user_id: int) -> list[dict]:
        """Pull price data grouped by query/category from user's searches."""
        conn = self.db.connect()

        # Get user's active search queries as categories
        searches = conn.execute(
            "SELECT id, query FROM searches WHERE user_id = ? AND active = 1",
            (user_id,),
        ).fetchall()

        categories = []
        for s in searches:
            search_id = s["id"]
            category = s["query"]

            # Recent prices (last 7 days)
            recent = conn.execute(
                """SELECT l.price FROM analysis an
                JOIN listings l ON an.listing_id = l.id
                WHERE an.search_id = ?
                AND an.analyzed_at > datetime('now', '-7 days')
                ORDER BY an.analyzed_at DESC LIMIT 50""",
                (search_id,),
            ).fetchall()

            # Previous period prices (7-14 days ago)
            prev = conn.execute(
                """SELECT l.price FROM analysis an
                JOIN listings l ON an.listing_id = l.id
                WHERE an.search_id = ?
                AND an.analyzed_at BETWEEN datetime('now', '-14 days') AND datetime('now', '-7 days')
                ORDER BY an.analyzed_at DESC LIMIT 50""",
                (search_id,),
            ).fetchall()

            # Hot deals count
            hot_count = conn.execute(
                """SELECT COUNT(*) FROM analysis
                WHERE search_id = ? AND deal_score >= 70
                AND analyzed_at > datetime('now', '-7 days')""",
                (search_id,),
            ).fetchone()[0]

            recent_prices = [r[0] for r in recent if r[0] > 0]
            prev_prices = [r[0] for r in prev if r[0] > 0]

            if recent_prices:
                categories.append({
                    "category": category,
                    "search_id": search_id,
                    "recent_prices": recent_prices,
                    "prev_prices": prev_prices,
                    "hot_deals_count": hot_count,
                })

        return categories

    def _compute_trends(self, categories: list[dict]) -> list[dict]:
        """Compute price trends without AI."""
        results = []
        for cat in categories:
            recent = cat["recent_prices"]
            prev = cat["prev_prices"]

            avg_recent = statistics.mean(recent) if recent else 0
            median_recent = statistics.median(recent) if recent else 0
            avg_prev = statistics.mean(prev) if prev else avg_recent

            if avg_prev > 0 and avg_recent > 0:
                trend_pct = (avg_recent - avg_prev) / avg_prev * 100
            else:
                trend_pct = 0.0

            if trend_pct > 3:
                trend = "rising"
                trend_emoji = "↑"
            elif trend_pct < -3:
                trend = "falling"
                trend_emoji = "↓"
            else:
                trend = "stable"
                trend_emoji = "→"

            if cat["hot_deals_count"] >= 3:
                trend_emoji = "🔥"

            results.append({
                "category": cat["category"],
                "avg_price": round(avg_recent),
                "median_price": round(median_recent),
                "sample_size": len(recent),
                "trend": trend,
                "trend_pct": round(trend_pct, 1),
                "trend_emoji": trend_emoji,
                "hot_deals_count": cat["hot_deals_count"],
                "comment": self._default_comment(trend, trend_pct, cat["hot_deals_count"]),
            })
        return results

    @staticmethod
    def _default_comment(trend: str, trend_pct: float, hot: int) -> str:
        """Generate heuristic comment without AI."""
        if hot >= 3:
            return f"🔥 {hot} горячих предложения прямо сейчас"
        if trend == "rising":
            return f"Цены растут {abs(trend_pct):.1f}% — стоит поторопиться"
        if trend == "falling":
            return f"Цены падают {abs(trend_pct):.1f}% — хороший момент для покупки"
        return "Рынок стабилен"

    async def build(self, user_id: int) -> list[MarketRadarSnapshot]:
        """Build Market Radar for a user. Uses AI if available."""
        raw_categories = self._get_category_data(user_id)
        if not raw_categories:
            return []

        computed = self._compute_trends(raw_categories)

        # Enrich with AI if available
        ai_items: list[MarketRadarItem] = []
        if self.ai and self.ai.is_available:
            try:
                # Send compact data to AI
                ai_input = [
                    {
                        "category": c["category"],
                        "avg_price_recent": c["avg_price"],
                        "trend_pct": c["trend_pct"],
                        "sample_size": c["sample_size"],
                        "hot_deals_count": c["hot_deals_count"],
                    }
                    for c in computed
                ]
                ai_items = await self.ai.generate_market_radar(ai_input)
            except Exception as e:
                log.warning("AI Market Radar failed: %s", e)

        # Build snapshots, merging AI comments where available
        ai_by_cat = {item.category: item for item in ai_items}
        snapshots = []
        for c in computed:
            ai = ai_by_cat.get(c["category"])
            snapshot = MarketRadarSnapshot(
                category=c["category"],
                avg_price=c["avg_price"],
                median_price=c["median_price"],
                sample_size=c["sample_size"],
                trend=ai.trend if ai else c["trend"],
                trend_pct=ai.trend_pct if ai else c["trend_pct"],
                trend_emoji=ai.trend_emoji if ai else c["trend_emoji"],
                ai_comment=ai.comment if ai else c["comment"],
                hot_deals_count=c["hot_deals_count"],
            )
            self.db.save_market_radar(user_id, snapshot)
            snapshots.append(snapshot)

        log.info("Market Radar built: %d categories for user %d", len(snapshots), user_id)
        return snapshots
