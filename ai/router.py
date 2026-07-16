"""AI Router — routes AI analysis requests to the appropriate provider and manages failover."""

from __future__ import annotations

import logging
from typing import Optional

from ai.base import AIProvider
from ai.factory import get_ai_provider, get_user_ai_provider
from database.base import BaseDatabase
from models import DealScore, RawListing

log = logging.getLogger("market_agent.ai.router")


class AIRouter:
    """Routes listing analysis requests to user-specific or global AI providers.

    Features:
    - User API Key isolation.
    - Automatic failover to global admin keys on user key exhaustion/error.
    - Estimates confidence & market liquidity.
    """

    def __init__(self, db: BaseDatabase):
        self.db = db

    async def analyze_listing(
        self,
        listing: RawListing,
        deal: DealScore,
        user_settings: dict,
    ) -> DealScore:
        """Route deal to the appropriate AI provider, perform analysis, and estimate metrics."""
        from analyzer.ai_scorer import AIScorer

        # 1. Estimate Market Liquidity based on database activity
        deal.market_liquidity = self._estimate_liquidity(listing.title, listing.price)

        # 2. Resolve AI Provider
        user_provider = self._get_user_provider(user_settings)
        ai_scorer: Optional[AIScorer] = None

        if user_provider:
            ai_scorer = AIScorer(self.db, user_provider)

        if not ai_scorer or not ai_scorer.enabled:
            # Fall back to global system provider directly if user has none configured
            global_provider = get_ai_provider()
            if global_provider:
                ai_scorer = AIScorer(self.db, global_provider)
                log.debug("Using global fallback AI provider for user %s", user_settings.get("user_id"))

        if not ai_scorer or not ai_scorer.enabled:
            # Heuristic-only mode, confidence is low
            deal.confidence = 0.4
            return deal

        # 3. Perform AI analysis with failover protection
        try:
            deal = await ai_scorer.enrich(deal, listing, user_settings)
            # If AI scoring succeeded, set a high confidence
            deal.confidence = 0.85
        except Exception as e:
            log.warning(
                "User AI provider failed for user %s: %s. Attempting failover to global keys...",
                user_settings.get("user_id"),
                e,
            )
            # Failover to global provider
            global_provider = get_ai_provider()
            if global_provider and (user_provider is None or global_provider.name != user_provider.name):
                try:
                    fallback_scorer = AIScorer(self.db, global_provider)
                    deal = await fallback_scorer.enrich(deal, listing, user_settings)
                    deal.confidence = 0.75  # Slightly lower confidence due to fallback
                    log.info("Failover to global AI provider succeeded for user %s", user_settings.get("user_id"))
                except Exception as ex:
                    log.error("Global failover AI provider also failed: %s", ex)
                    deal.confidence = 0.4
            else:
                deal.confidence = 0.4

        return deal

    def _estimate_liquidity(self, category: str, price: float) -> str:
        """Estimate market liquidity ('high' | 'medium' | 'low') based on historical samples."""
        try:
            listings = self.db.get_listings_for_price_analysis(
                category=category,
                max_price=price * 2 if price > 0 else 1_000_000,
                limit=100,
            )
            count = len(listings)
            if count >= 15:
                return "high"
            elif count >= 5:
                return "medium"
            return "low"
        except Exception:
            return "medium"

    def _get_user_provider(self, user_settings: dict) -> Optional[AIProvider]:
        """Resolve AI provider based on user settings."""
        provider_name = user_settings.get("ai_provider", "")
        api_key = user_settings.get("ai_api_key", "")
        model = user_settings.get("ai_model", "")

        if provider_name and api_key:
            try:
                return get_ai_provider(provider_name=provider_name, api_key=api_key, model=model)
            except Exception as e:
                log.warning("Failed to instantiate user-configured AI provider '%s': %s", provider_name, e)
        return None
