"""Opportunity Engine — groups similar listings into business opportunities."""

from __future__ import annotations

import logging
from typing import Optional

from database.base import BaseDatabase
from models import DealScore, RawListing

log = logging.getLogger("market_agent.analyzer.opportunity")


class OpportunityEngine:
    """Groups incoming processed listings into logical multi-listing Opportunities."""

    def __init__(self, db: BaseDatabase):
        self.db = db

    def process_listing_deal(
        self,
        user_id: int,
        listing_id: int,
        listing: RawListing,
        deal: DealScore,
    ) -> tuple[dict, bool, bool]:
        """Process a listing and its analysis score, grouping it into an Opportunity.

        Returns:
            (opportunity_dict, is_new, price_improved)
        """
        # Try to find a matching opportunity
        opp = self.db.find_matching_opportunity(user_id, listing.title, listing.price)

        if opp:
            is_new = False
            price_improved = listing.price < opp["best_price"]

            # Update existing opportunity
            listings_count = opp["listings_count"] + 1
            best_price = min(opp["best_price"], listing.price)
            avg_price = (opp["avg_price"] * opp["listings_count"] + listing.price) / listings_count

            # Determine recommendation & URL from the best listing
            is_better_deal = listing.price <= opp["best_price"] or deal.score > opp["deal_score"]
            recommendation = deal.recommendation if is_better_deal else opp["recommendation"]
            url = listing.url if listing.price <= opp["best_price"] else opp["url"]
            deal_score = max(opp["deal_score"], deal.score)
            confidence = max(opp["confidence"], deal.confidence)

            self.db.update_opportunity(
                opp["id"],
                best_price=best_price,
                avg_price=avg_price,
                deal_score=deal_score,
                confidence=confidence,
                market_liquidity=deal.market_liquidity,
                recommendation=recommendation,
                url=url,
                listings_count=listings_count,
            )

            # Link listing to opportunity
            self.db.link_listing_to_opportunity(listing_id, opp["id"])

            log.info(
                "Grouped listing '%s' (price %s) into existing Opportunity #%s (new count: %s)",
                listing.title[:50],
                listing.price,
                opp["id"],
                listings_count,
            )
            # Retrieve updated version
            updated_opp = self.db.get_opportunity(opp["id"])
            return updated_opp or opp, is_new, price_improved
        else:
            is_new = True
            price_improved = True

            # Create a new opportunity
            opp_data = {
                "user_id": user_id,
                "title": listing.title,
                "category": listing.title,  # default fallback
                "best_price": listing.price,
                "avg_price": listing.price,
                "median_price": deal.market_price,
                "deal_score": deal.score,
                "confidence": deal.confidence,
                "market_liquidity": deal.market_liquidity,
                "recommendation": deal.recommendation,
                "url": listing.url,
                "listings_count": 1,
            }
            opp_id = self.db.create_opportunity(opp_data)

            # Link listing to opportunity
            self.db.link_listing_to_opportunity(listing_id, opp_id)

            log.info(
                "Created new Opportunity #%s for listing '%s' (price %s)",
                opp_id,
                listing.title[:50],
                listing.price,
            )
            opp_data["id"] = opp_id
            return opp_data, is_new, price_improved
