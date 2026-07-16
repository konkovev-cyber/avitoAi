"""Scheduler v2 — orchestrates collection + AI analysis + alerts + Market Radar.

Improvements over v1:
- Per-user Hunter Mode intervals (not global)
- AI-enriched deal scoring via DealEngine.evaluate_async()
- Market Radar rebuild every hour
- Sends push notifications via bot application
- Respects user notification settings
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional

from config import settings
from database.db import Database
from models import SearchQuery
from collector.avito import AvitoCollector
from collector.youla import YulaCollector
from analyzer.engine import DealEngine

log = logging.getLogger("market_agent.scheduler")

RADAR_REBUILD_INTERVAL = 3600  # rebuild Market Radar every hour


class Scheduler:
    """Orchestrates periodic collection + analysis + alerts."""

    def __init__(self, db: Database, bot_app=None):
        self.db = db
        self.bot_app = bot_app           # telegram Application (optional, for push alerts)
        self._collectors: dict = {}
        self._running = False
        self._last_radar_build: float = 0.0
        self._last_run_times: dict[int, float] = {}  # search_id -> timestamp

        from analyzer.opportunity import OpportunityEngine
        self._opp_engine = OpportunityEngine(db)

        # Build AI scorer if configured
        ai_scorer = None
        try:
            from ai.factory import get_ai_provider
            from analyzer.ai_scorer import AIScorer
            ai_prov = get_ai_provider()
            if ai_prov:
                ai_scorer = AIScorer(db, ai_prov)
                log.info("AI scorer enabled: %s", ai_prov.name)
        except Exception as e:
            log.warning("AI scorer init failed: %s", e)

        self._engine = DealEngine(db, ai_scorer=ai_scorer)

    async def run(self):
        import os

        self._running = True
        self._queue = asyncio.Queue()
        self._active_processing_searches = set()
        self._users_processed = set()

        max_workers = int(os.getenv("MA_MAX_WORKERS", "2"))
        log.info(
            "Scheduler started (avito=%s, youla=%s, AI=%s, workers=%d)",
            settings.collector_avito_enabled,
            settings.collector_youla_enabled,
            "yes" if self._engine.ai_scorer else "no",
            max_workers,
        )

        # Spawn workers
        workers = []
        for i in range(max_workers):
            t = asyncio.create_task(self._worker(i))
            workers.append(t)

        try:
            while self._running:
                await self._run_cycle()

                # Rebuild Market Radar once per hour for processed users
                if time.time() - self._last_radar_build > RADAR_REBUILD_INTERVAL:
                    if self._users_processed:
                        await self._rebuild_radar(list(self._users_processed))
                        self._users_processed.clear()
                    self._last_radar_build = time.time()

                await asyncio.sleep(settings.collector_interval_sec)
        except asyncio.CancelledError:
            log.info("Scheduler cancelled")
        finally:
            self._running = False
            # Push sentinels to shutdown workers cleanly
            for _ in range(max_workers):
                await self._queue.put(None)
            # Wait for workers to exit
            await asyncio.gather(*workers, return_exceptions=True)
            log.info("Scheduler stopped")

    async def _run_cycle(self):
        """Producer: checks active searches, filters due ones, and pushes to queue."""
        searches = self.db.get_active_searches()
        if not searches:
            log.debug("No active searches, skipping cycle")
            return

        now = time.time()
        pushed_count = 0

        for search_row in searches:
            search_id = search_row["id"]
            user_id = search_row["user_id"]

            if search_id in self._active_processing_searches:
                continue

            u_settings = self.db.get_user_settings(user_id)
            interval = u_settings.get("collector_interval_sec", 300)
            last_run = self._last_run_times.get(search_id, 0.0)

            if now - last_run < interval:
                continue

            self._last_run_times[search_id] = now
            self._active_processing_searches.add(search_id)
            await self._queue.put((search_row, u_settings))
            pushed_count += 1

        if pushed_count > 0:
            log.info("Queued %d active search tasks for workers", pushed_count)

    async def _worker(self, worker_id: int):
        """Worker task that consumes searches from queue and performs scraping & analysis."""
        from collector.avito import AvitoCollector
        from collector.youla import YulaCollector

        worker_collectors = {}

        async def get_worker_collector(name: str):
            if name not in worker_collectors:
                proxy = settings.proxy_url
                if name == "avito" and settings.collector_avito_enabled:
                    worker_collectors[name] = AvitoCollector(proxy_url=proxy)
                elif name == "youla" and settings.collector_youla_enabled:
                    worker_collectors[name] = YulaCollector(proxy_url=proxy)
            return worker_collectors.get(name)

        log.info("Worker #%d started", worker_id)

        try:
            while self._running:
                task = await self._queue.get()
                if task is None:
                    self._queue.task_done()
                    break

                search_row, u_settings = task
                search_id = search_row["id"]

                try:
                    await self._process_search(search_row, u_settings, get_worker_collector)
                except Exception as e:
                    log.error("Worker #%d failed processing search %s: %s", worker_id, search_id, e)
                finally:
                    self._active_processing_searches.discard(search_id)
                    self._queue.task_done()
        except asyncio.CancelledError:
            log.debug("Worker #%d cancelled", worker_id)
        finally:
            # Clean up worker's browsers
            for name, c in worker_collectors.items():
                try:
                    await c.close()
                except Exception as e:
                    log.warning("Worker #%d failed closing collector %s: %s", worker_id, name, e)
            worker_collectors.clear()
            log.info("Worker #%d stopped and cleaned up", worker_id)

    async def _process_search(self, search_row: dict, u_settings: dict, get_collector_func):
        """Perform actual collection + analysis for a single search."""
        user_id = search_row["user_id"]
        min_score = u_settings.get("hunter_min_score", 50.0)
        min_savings = u_settings.get("hunter_min_savings_pct", 10.0)
        notify = bool(u_settings.get("notifications_enabled", 1))

        sources = []
        if u_settings.get("sources_avito", 1):
            sources.append("avito")
        if u_settings.get("sources_youla", 1):
            sources.append("youla")

        if not sources:
            return

        query = SearchQuery(
            user_id=user_id,
            query=search_row["query"],
            category=search_row.get("category"),
            keywords=json.loads(search_row.get("keywords") or "[]"),
            max_price=search_row.get("max_price"),
            min_price=search_row.get("min_price"),
            location=search_row.get("location"),
            condition=search_row.get("condition", "any"),
            purpose=search_row.get("purpose", "self"),
            sources=sources,
        )

        for source in query.sources:
            collector = await get_collector_func(source)
            if collector is None:
                continue

            log.info("[%s] Searching: %s (user=%d)", source, query.query, user_id)
            try:
                listings = await collector.search(query)
            except Exception as e:
                log.error("Collector %s failed for %s: %s", source, query.query, e)
                continue

            new_count = 0
            alert_count = 0

            for listing in listings:
                if self.db.listing_exists(listing.url):
                    continue

                listing_id = self.db.insert_listing(listing)
                if not listing_id:
                    continue
                new_count += 1

                # AI-enriched analysis (async, with fallback to heuristics)
                try:
                    deal = await self._engine.evaluate_async(listing, search_row["id"])
                except Exception as e:
                    log.warning("Analysis failed for %s: %s", listing.title[:50], e)
                    deal = self._engine.evaluate(listing, search_row["id"])

                analysis_id = self.db.save_analysis(listing_id, search_row["id"], deal)

                # Group into opportunity
                opp, is_new, price_improved = self._opp_engine.process_listing_deal(
                    user_id, listing_id, listing, deal
                )

                # Check thresholds on the opportunity level
                opp_savings_pct = (
                    (opp["median_price"] - opp["best_price"]) / opp["median_price"] * 100
                    if opp["median_price"] > 0
                    else 0
                )
                passes_score = opp["deal_score"] >= min_score
                passes_savings = abs(opp_savings_pct) >= min_savings
                is_good = opp["recommendation"] in ("buy", "maybe")

                if is_good and passes_score and passes_savings and (is_new or price_improved):
                    # Save alert to DB
                    self.db.save_alert(user_id, analysis_id)
                    alert_count += 1

                    # Push notification
                    if notify and self.bot_app:
                        telegram_id = self._get_telegram_id(user_id)
                        if telegram_id:
                            await self._push_alert(telegram_id, opp, deal, opp_savings_pct)

                    emoji = "🔥" if opp["recommendation"] == "buy" else "✅"
                    log.info(
                        "%s OPPORTUNITY [%.0f] %s — Best: %s₽ (Market: %s₽, %+.0f%%)",
                        emoji, opp["deal_score"],
                        opp["title"][:50],
                        f"{opp['best_price']:,.0f}",
                        f"{opp['median_price']:,.0f}",
                        -opp_savings_pct,
                    )

            log.info("  → %s: %d new / %d alerts", source, new_count, alert_count)
            self._users_processed.add(user_id)

    def _get_telegram_id(self, user_id: int) -> Optional[int]:
        """Get Telegram ID for a DB user ID."""
        try:
            conn = self.db.connect()
            row = conn.execute(
                "SELECT telegram_id FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return row["telegram_id"] if row else None
        except Exception:
            return None

    async def _push_alert(self, telegram_id: int, opp: dict, deal, savings_pct: float):
        """Push a deal alert to Telegram."""
        try:
            from bot.telegram import send_deal_alert
            title = opp["title"]
            if opp["listings_count"] > 1:
                title = f"{title} (и еще {opp['listings_count'] - 1} продавца)"

            alert_data = {
                "title": title,
                "price": opp["best_price"],
                "market_price": opp["median_price"],
                "deal_score": opp["deal_score"],
                "price_delta_pct": -savings_pct,
                "risk_score": deal.risk_score,
                "recommendation": opp["recommendation"],
                "ai_explanation": deal.ai_explanation or "",
                "ai_why_good": deal.ai_why_good or [],
                "ai_risks": deal.ai_risks or [],
                "ai_score": opp["deal_score"],
                "url": opp["url"],
                "confidence": opp["confidence"],
                "market_liquidity": opp["market_liquidity"],
            }
            await send_deal_alert(self.bot_app, telegram_id, alert_data)
        except Exception as e:
            log.warning("Push alert failed for tg=%s: %s", telegram_id, e)

    async def _rebuild_radar(self, user_ids: list[int]):
        """Rebuild Market Radar for all active users."""
        try:
            from ai.factory import get_ai_provider
            from analyzer.market_radar import MarketRadar
            ai_prov = get_ai_provider()
            radar = MarketRadar(self.db, ai_provider=ai_prov)
            for user_id in user_ids:
                try:
                    snapshots = await radar.build(user_id)
                    if snapshots:
                        log.info(
                            "Market Radar: %d categories for user %d",
                            len(snapshots), user_id
                        )
                except Exception as e:
                    log.warning("Radar build failed for user %d: %s", user_id, e)
        except Exception as e:
            log.warning("Market Radar rebuild error: %s", e)

    def stop(self):
        self._running = False

