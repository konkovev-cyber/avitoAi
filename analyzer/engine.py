"""Deal Scoring Engine — evaluates how good a deal is."""

from __future__ import annotations

import logging

from config import settings
from database.db import Database
from models import DealScore, RawListing, PriceStats, RiskScore
from .price import PriceModel
from .risk import RiskScorer

log = logging.getLogger("market_agent.analyzer.engine")


class DealEngine:
    """Combines price analysis + risk scoring into a single deal score."""

    # Weights
    W_PRICE = 0.50  # price advantage weight
    W_RISK = 0.30  # risk penalty weight
    W_QUALITY = 0.20  # listing quality weight

    def __init__(self, db: Database):
        self.db = db
        self.price_model = PriceModel(db)
        self.risk_scorer = RiskScorer()

    def evaluate(
        self, listing: RawListing, search_id: int
    ) -> DealScore:
        """Evaluate a single listing. Returns score + recommendation."""
        # 1. Market price analysis
        market = self.price_model.estimate(
            category=listing.title,  # use title as category proxy
            max_price=listing.price * 2 if listing.price > 0 else 1000000,
        )

        # 2. Risk scoring
        risk = self.risk_scorer.score(listing, market.median)

        # 3. Calculate price delta
        market_price = market.median if market.sample_size > 0 else listing.price
        if market_price > 0 and listing.price > 0:
            price_delta = (market_price - listing.price) / market_price * 100
        else:
            price_delta = 0.0

        # 4. Listing quality (simple heuristic)
        quality = 50.0
        if listing.description and len(listing.description) > 100:
            quality += 20
        if listing.images:
            quality += 15
        if listing.seller_name:
            quality += 15

        # 5. Compute deal score
        price_score = max(0, min(100, price_delta * 2))  # 0% delta = 0, 50% delta = 100
        score = (
            self.W_PRICE * price_score
            - self.W_RISK * risk.score
            + self.W_QUALITY * quality
        )
        score = max(0, min(100, score))

        # 6. Determine recommendation
        if score >= settings.deal_score_threshold_buy:
            recommendation = "buy"
        elif score >= settings.deal_score_threshold_maybe:
            recommendation = "maybe"
        else:
            recommendation = "skip"

        self.log_result(listing, score, price_delta, risk, recommendation)

        return DealScore(
            score=round(score, 1),
            market_price=round(market_price, 2),
            price_delta_pct=round(price_delta, 1),
            risk_score=round(risk.score, 1),
            risk_factors=risk.factors,
            recommendation=recommendation,
        )

    def log_result(
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
