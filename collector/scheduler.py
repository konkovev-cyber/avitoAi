"""Scheduler — runs collectors periodically + analyzes + alerts."""

from __future__ import annotations

import asyncio
import json
import logging

from config import settings
from database.db import Database
from models import SearchQuery, RawListing
from collector.avito import AvitoCollector
from collector.youla import YulaCollector
from analyzer.engine import DealEngine
from bot.alerts import format_alert

log = logging.getLogger("market_agent.scheduler")


class Scheduler:
    """Orchestrates periodic collection + analysis + alerts."""

    def __init__(self, db: Database):
        self.db = db
        self._collectors: dict[str, any] = {}
        self._running = False
        self._engine = DealEngine(db)

    async def _get_collector(self, name: str):
        if name not in self._collectors:
            proxy = settings.proxy_url
            if name == "avito" and settings.collector_avito_enabled:
                self._collectors[name] = AvitoCollector(proxy_url=proxy)
            elif name == "youla" and settings.collector_youla_enabled:
                self._collectors[name] = YulaCollector(proxy_url=proxy)
        return self._collectors.get(name)

    async def run(self):
        self._running = True
        log.info(
            "Scheduler started (interval=%ds, avito=%s, youla=%s)",
            settings.collector_interval_sec,
            settings.collector_avito_enabled,
            settings.collector_youla_enabled,
        )

        try:
            while self._running:
                searches = self.db.get_active_searches()
                if not searches:
                    log.info("No active searches, waiting...")
                    await asyncio.sleep(settings.collector_interval_sec)
                    continue

                for search_row in searches:
                    query = SearchQuery(
                        user_id=search_row["user_id"],
                        query=search_row["query"],
                        category=search_row.get("category"),
                        keywords=json.loads(search_row.get("keywords", "[]")),
                        max_price=search_row.get("max_price"),
                        min_price=search_row.get("min_price"),
                        location=search_row.get("location"),
                        sources=["avito", "youla"],
                    )

                    for source in query.sources:
                        collector = await self._get_collector(source)
                        if collector is None:
                            continue

                        log.info("[%s] Searching: %s", source, query.query)
                        listings = await collector.search(query)

                        new_count = 0
                        alert_count = 0
                        for listing in listings:
                            # Skip duplicates
                            if self.db.listing_exists(listing.url):
                                continue

                            listing_id = self.db.insert_listing(listing)
                            if not listing_id:
                                continue
                            new_count += 1

                            # Analyze deal
                            deal = self._engine.evaluate(listing, search_row["id"])
                            analysis_id = self.db.save_analysis(listing_id, search_row["id"], deal)

                            # Alert if good deal
                            if deal.recommendation in ("buy", "maybe"):
                                self.db.save_alert(search_row["user_id"], analysis_id)
                                alert_count += 1

                                # Log
                                emoji = "🔥" if deal.recommendation == "buy" else "✅"
                                log.info(
                                    "%s DEAL [%.0f] %s — %s₽ (%+.0f%%) → %s",
                                    emoji,
                                    deal.score,
                                    listing.title[:50],
                                    f"{listing.price:,.0f}",
                                    deal.price_delta_pct,
                                    deal.recommendation.upper(),
                                )

                        log.info(
                            "  → %s: %d new / %d alerts",
                            source, new_count, alert_count,
                        )

                log.info("Cycle complete. Next in %ds", settings.collector_interval_sec)
                await asyncio.sleep(settings.collector_interval_sec)

        except asyncio.CancelledError:
            log.info("Scheduler cancelled")
        finally:
            await self._close_all()

    async def _close_all(self):
        for name, c in self._collectors.items():
            try:
                await c.close()
            except Exception as e:
                log.warning("Error closing %s: %s", name, e)
        self._collectors.clear()
        log.info("All collectors closed")

    def stop(self):
        self._running = False
