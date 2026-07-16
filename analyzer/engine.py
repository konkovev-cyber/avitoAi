"""Deal Scoring Engine — evaluates how good a deal is.

Two-layer scoring:
1. Heuristic (always runs): price delta + risk + quality
2. AI (optional): blended when provider configured

The engine works identically without AI — it simply returns heuristic scores.
"""

from __future__ import annotations

import logging
from typing import Optional

from config import settings
from database.db import Database
from models import DealScore, RawListing, PriceStats, RiskScore
from .price import PriceModel
from .risk import RiskScorer

log = logging.getLogger("market_agent.analyzer.engine")


class DealEngine:
    """Combines price analysis + risk scoring into a single deal score.

    Optionally enriches with AI if ai_scorer is provided.
    """

    # Heuristic weights
    W_PRICE = 0.50
    W_RISK = 0.30
    W_QUALITY = 0.20

    def __init__(self, db: Database, ai_scorer=None):
        self.db = db
        self.price_model = PriceModel(db)
        self.risk_scorer = RiskScorer()
        self.ai_scorer = ai_scorer  # Optional[AIScorer]

    def evaluate(self, listing: RawListing, search_id: int) -> DealScore:
        """Synchronous heuristic-only evaluation. Returns DealScore."""
        # 1. Market price analysis
        market = self.price_model.estimate(
            category=listing.title,
            max_price=listing.price * 2 if listing.price > 0 else 1_000_000,
        )

        # 2. Risk scoring
        risk = self.risk_scorer.score(listing, market.median)

        # 3. Price delta
        market_price = market.median if market.sample_size > 0 else listing.price
        if market_price > 0 and listing.price > 0:
            price_delta = (market_price - listing.price) / market_price * 100
        else:
            price_delta = 0.0

        # 4. Listing quality heuristic
        quality = 50.0
        if listing.description and len(listing.description) > 100:
            quality += 20
        if listing.images:
            quality += 15
        if listing.seller_name:
            quality += 15

        # 5. Compute deal score
        price_score = max(0, min(100, price_delta * 2))
        score = (
            self.W_PRICE * price_score
            - self.W_RISK * risk.score
            + self.W_QUALITY * quality
        )
        score = max(0, min(100, score))

        # 6. Recommendation
        if score >= settings.deal_score_threshold_buy:
            recommendation = "buy"
        elif score >= settings.deal_score_threshold_maybe:
            recommendation = "maybe"
        else:
            recommendation = "skip"

        deal = DealScore(
            score=round(score, 1),
            market_price=round(market_price, 2),
            price_delta_pct=round(price_delta, 1),
            risk_score=round(risk.score, 1),
            risk_factors=risk.factors,
            recommendation=recommendation,
        )

        self._log_result(listing, score, price_delta, risk, recommendation)
        return deal

    async def evaluate_async(self, listing: RawListing, search_id: int) -> DealScore:
        """Async evaluation: heuristics + optional AI enrichment."""
        deal = self.evaluate(listing, search_id)

        # Enrich with AI if configured
        if self.ai_scorer and self.ai_scorer.enabled:
            deal = await self.ai_scorer.enrich(deal, listing)

        return deal

    def _log_result(
        self,
        listing: RawListing,
        score: float,
        price_delta: float,
        risk: RiskScore,
        recommendation: str,
    ):
        emoji = {"buy": "🔥", "maybe": "✅", "skip": "⏭"}.get(recommendation, "❓")
        log.info(
            "%s [%.0f] %s — %.0f%% от рынка, риск %.0f — %s",
            emoji,
            score,
            listing.title[:60],
            price_delta,
            risk.score,
            recommendation.upper(),
        )
