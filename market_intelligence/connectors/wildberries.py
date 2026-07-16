"""Wildberries Connector — Commerce (бренды, магазины, товары)."""

from __future__ import annotations

import hashlib
from typing import Optional

from ..models.offer import Offer
from ..models.evidence import Evidence
from .base import (
    BaseConnector,
    ConnectorResult,
    ConnectorCapabilities,
    ConnectorLimitations,
)


class WildberriesConnector(BaseConnector):
    """Connector для Wildberries.

    Commerce-источник. Продавец = магазин.
    Сигналы: seller_name, brand, category, rating.
    Контакты: скрыты. Бренд ≠ продавец.
    """

    def __init__(self):
        super().__init__()
        self.name = "wildberries"

    def collect(self, query: str, test_data: Optional[list[dict]] = None, **kwargs) -> ConnectorResult:
        if test_data is not None:
            return self._collect_from_test_data(test_data)
        return ConnectorResult()

    def _collect_from_test_data(self, items: list[dict]) -> ConnectorResult:
        result = ConnectorResult()
        for item in items:
            offer = self.normalize(item)
            listing = offer.to_listing()
            evidence = self.extract_evidence(offer)
            result.listings.append(listing)
            result.evidence.extend(evidence)
        return result

    def normalize(self, raw: dict) -> Offer:
        offer_id = self._make_id(raw)
        return Offer(
            id=offer_id,
            source="wildberries",
            url=raw.get("url", ""),
            title=raw.get("title", "Товар без названия"),
            seller_name=raw.get("seller_name", raw.get("store_name", "")),
            seller_url=raw.get("seller_url", ""),
            sku=raw.get("sku", raw.get("nm_id", "")),
            brand=raw.get("brand", ""),
            category=raw.get("category", "Бытовая техника"),
            price=raw.get("price"),
            description=raw.get("description", ""),
            rating=raw.get("rating"),
            reviews_count=raw.get("reviews_count"),
            phone=raw.get("phone"),
            website=raw.get("website"),
            images=raw.get("images", []),
            raw_data=raw,
        )

    def extract_evidence(self, offer: Offer) -> list[Evidence]:
        evidence = []

        if offer.seller_name:
            evidence.append(Evidence(
                id=f"ev_{offer.id}_store_{self._hash(offer.seller_name)[:8]}",
                type="name_extracted",
                source_listing=offer.id,
                value=offer.seller_name,
                field="seller_name",
                strength=0.25,
                confidence=0.75,
                extraction_method="api_field",
            ))

        if offer.brand:
            evidence.append(Evidence(
                id=f"ev_{offer.id}_brand_{self._hash(offer.brand)[:8]}",
                type="category_extracted",
                source_listing=offer.id,
                value=offer.brand,
                field="brand",
                strength=0.12,
                confidence=0.70,
                extraction_method="api_field",
            ))

        if offer.sku:
            evidence.append(Evidence(
                id=f"ev_{offer.id}_sku_{self._hash(offer.sku)[:8]}",
                type="category_extracted",
                source_listing=offer.id,
                value=offer.sku,
                field="sku",
                strength=0.05,
                confidence=0.95,
                extraction_method="api_field",
            ))

        if offer.rating is not None:
            evidence.append(Evidence(
                id=f"ev_{offer.id}_rating_{self._hash(str(offer.rating))[:8]}",
                type="category_extracted",
                source_listing=offer.id,
                value=str(offer.rating),
                field="rating",
                strength=0.08,
                confidence=0.85,
                extraction_method="api_field",
            ))

        if offer.phone:
            evidence.append(Evidence(
                id=f"ev_{offer.id}_phone_{self._hash(offer.phone)[:8]}",
                type="phone_extracted",
                source_listing=offer.id,
                value=offer.phone,
                field="phone",
                strength=0.35,
                confidence=0.85,
                extraction_method="html_parse",
            ))

        if offer.website:
            evidence.append(Evidence(
                id=f"ev_{offer.id}_web_{self._hash(offer.website)[:8]}",
                type="website_extracted",
                source_listing=offer.id,
                value=offer.website,
                field="website",
                strength=0.35,
                confidence=0.85,
                extraction_method="html_parse",
            ))

        return evidence

    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            fields=["seller_name", "store_name", "title", "sku", "nm_id",
                    "brand", "category", "price", "rating", "reviews_count"],
            search_modes=["by_query", "by_category", "by_store"],
            rate_limit="8/min",
            requires_proxy=False,
        )

    def limitations(self) -> ConnectorLimitations:
        return ConnectorLimitations(
            never_available=["email", "inn", "address", "working_hours", "phone"],
            sometimes_available=["website"],
            legal_restrictions=[],
        )

    @staticmethod
    def _make_id(raw: dict) -> str:
        raw_str = f"wb_{raw.get('url', '')}_{raw.get('sku', raw.get('nm_id', ''))}"
        h = hashlib.sha256(raw_str.encode()).hexdigest()[:12]
        return f"wb_{h}"

    @staticmethod
    def _hash(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()
