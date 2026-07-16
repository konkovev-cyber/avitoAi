"""Risk scoring for listings."""

from __future__ import annotations

import logging
from datetime import datetime

from models import RawListing, RiskScore

log = logging.getLogger("market_agent.analyzer.risk")


class RiskScorer:
    """Evaluates risk factors for a listing."""

    def score(self, listing: RawListing, market_price: float) -> RiskScore:
        """Score risk 0-100 based on listing quality."""
        factors = []
        score = 0.0

        # Price too good to be true
        if market_price > 0 and listing.price > 0:
            ratio = listing.price / market_price
            if ratio < 0.5:
                score += 25
                factors.append("Цена значительно ниже рынка (>50%) — вероятен обман")
            elif ratio < 0.7:
                score += 15
                factors.append("Цена ниже рынка на 30-50% — стоит проверить")

        # No description
        if not listing.description or len(listing.description.strip()) < 20:
            score += 10
            factors.append("Нет описания")

        # No images
        if not listing.images:
            score += 15
            factors.append("Нет фотографий")

        # Seller issues
        if listing.seller_name is None or listing.seller_name == "":
            score += 5
            factors.append("Продавец не указан")

        if listing.seller_rating is not None and listing.seller_rating < 3.0:
            score += 10
            factors.append("Низкий рейтинг продавца")

        if listing.seller_deals_count is not None and listing.seller_deals_count < 5:
            score += 5
            factors.append("Мало сделок у продавца")

        # Clamp
        score = min(score, 100.0)
        return RiskScore(score=score, factors=factors)
