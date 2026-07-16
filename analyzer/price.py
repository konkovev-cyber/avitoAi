"""Market price estimation from collected listings."""

from __future__ import annotations

import logging
import statistics

from config import settings
from database.db import Database
from models import PriceStats

log = logging.getLogger("market_agent.analyzer.price")


class PriceModel:
    """Estimates market price from similar listings."""

    def __init__(self, db: Database):
        self.db = db

    def estimate(self, category: str, max_price: float) -> PriceStats:
        """Compute market price statistics from similar listings."""
        listings = self.db.get_listings_for_price_analysis(
            category=category,
            max_price=max_price,
            limit=200,
        )

        prices = [l["price"] for l in listings if l["price"] > 0]

        if len(prices) < settings.min_listings_for_analysis:
            log.info(
                "Not enough data for price estimation: %d samples (need %d)",
                len(prices),
                settings.min_listings_for_analysis,
            )
            return PriceStats(sample_size=len(prices))

        prices.sort()
        n = len(prices)
        return PriceStats(
            median=statistics.median(prices),
            mean=statistics.mean(prices),
            p10=prices[int(n * 0.10)],
            p25=prices[int(n * 0.25)],
            p75=prices[int(n * 0.75)],
            p90=prices[int(n * 0.90)],
            std=statistics.stdev(prices) if n > 1 else 0.0,
            sample_size=n,
        )
