"""AI Scorer — enriches DealScore with AI analysis when a provider is available.

Design:
- Always optional: returns None if no AI provider configured
- Caches results in DB to avoid repeated API calls for same listing
- Falls back gracefully on any API error
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from ai.base import AIAnalysis, AIProvider
from database.db import Database
from models import DealScore, RawListing

log = logging.getLogger("market_agent.analyzer.ai_scorer")


class AIScorer:
    """Enriches deal scores with AI analysis."""

    def __init__(self, db: Database, provider: Optional[AIProvider] = None):
        self.db = db
        self.provider = provider

    @property
    def enabled(self) -> bool:
        return self.provider is not None and self.provider.is_available

    def _cache_key(self, listing: RawListing, market_price: float) -> str:
        raw = f"{listing.url}|{listing.price}|{market_price:.0f}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    async def enrich(self, deal: DealScore, listing: RawListing, user_settings: Optional[dict] = None) -> DealScore:
        """Add AI analysis to an existing DealScore. Returns enriched DealScore."""
        if not self.enabled:
            return deal

        cache_key = self._cache_key(listing, deal.market_price)

        # Check cache first
        cached = self.db.get_ai_cache(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                deal.ai_score = data.get("ai_score")
                deal.ai_explanation = data.get("explanation", "")
                deal.ai_why_good = data.get("why_good", [])
                deal.ai_risks = data.get("risks", [])
                deal.ai_provider = data.get("provider", "")
                log.debug("AI cache hit for %s", listing.title[:50])
                return deal
            except Exception:
                pass

        # Call AI provider
        try:
            analysis: AIAnalysis = await self.provider.analyze_listing(
                title=listing.title,
                price=listing.price,
                market_price=deal.market_price,
                description=listing.description or "",
                seller_name=listing.seller_name or "",
                seller_rating=listing.seller_rating,
                images_count=len(listing.images),
                similar_count=0,  # will be filled by engine
                price_delta_pct=deal.price_delta_pct,
            )

            deal.ai_score = analysis.ai_score
            deal.ai_explanation = analysis.explanation
            deal.ai_why_good = analysis.why_good
            deal.ai_risks = analysis.risks
            deal.ai_provider = analysis.provider

            # If AI recommendation is stronger than heuristic, blend scores
            if analysis.ai_score > 0 and analysis.confidence > 0.6:
                blended = deal.score * 0.6 + analysis.ai_score * 0.4
                deal.score = round(min(100, max(0, blended)), 1)
                # Update recommendation based on blended score
                u_set = user_settings or {}
                threshold_buy = u_set.get("threshold_buy", 70.0)
                threshold_maybe = u_set.get("threshold_maybe", 50.0)
                if deal.score >= threshold_buy:
                    deal.recommendation = "buy"
                elif deal.score >= threshold_maybe:
                    deal.recommendation = "maybe"

            # Cache the result
            cache_data = {
                "ai_score": analysis.ai_score,
                "explanation": analysis.explanation,
                "why_good": analysis.why_good,
                "risks": analysis.risks,
                "provider": analysis.provider,
            }
            self.db.set_ai_cache(
                cache_key,
                provider=analysis.provider,
                response=json.dumps(cache_data, ensure_ascii=False),
            )
            log.info(
                "AI scored: %s → %.0f/100 (%s)",
                listing.title[:50], analysis.ai_score, analysis.recommendation
            )

        except Exception as e:
            log.warning("AI scoring failed for %s: %s", listing.title[:50], e)

        return deal

    async def get_explanation(
        self,
        listing: RawListing,
        deal: DealScore,
        similar_count: int,
        percentile_position: float = 0.5,
    ) -> str:
        """Generate a standalone explanation for a deal card."""
        if not self.enabled:
            # Heuristic fallback explanation
            cheaper_pct = int(percentile_position * 100)
            savings = deal.market_price - listing.price
            return (
                f"Я сравнил {similar_count} похожих объявлений. "
                f"Средняя цена {deal.market_price:,.0f} ₽. "
                f"Это предложение дешевле {cheaper_pct}% рынка"
                + (f" — экономия {savings:,.0f} ₽." if savings > 0 else ".")
            )

        try:
            return await self.provider.explain_deal(
                title=listing.title,
                price=listing.price,
                market_price=deal.market_price,
                similar_count=similar_count,
                price_delta_pct=deal.price_delta_pct,
                percentile_position=percentile_position,
            )
        except Exception as e:
            log.warning("Failed to get AI explanation: %s", e)
            return ""
