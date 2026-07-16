"""Yandex Market Connector — Commerce Intelligence (магазины, бренды, товары)."""

from __future__ import annotations

import hashlib
import re
from typing import Optional

from ..models.listing import Listing
from ..models.evidence import Evidence
from .base import (
    BaseConnector,
    ConnectorResult,
    ConnectorCapabilities,
    ConnectorLimitations,
)


class YandexMarketConnector(BaseConnector):
    """
    Connector для Яндекс Маркета.

    Commerce-источник: продавец = магазин.
    Сигналы: название магазина, бренды, категории товаров, рейтинг.
    Контакты: обычно скрыты (нет телефона/email напрямую).
    """

    def __init__(self):
        super().__init__()
        self.name = "yandex_market"

    def collect(self, query: str, test_data: Optional[list[dict]] = None, **kwargs) -> ConnectorResult:
        if test_data is not None:
            return self._collect_from_test_data(test_data)
        return ConnectorResult()

    def _collect_from_test_data(self, items: list[dict]) -> ConnectorResult:
        result = ConnectorResult()
        for item in items:
            listing = self.normalize(item)
            evidence = self.extract_evidence(listing)
            result.listings.append(listing)
            result.evidence.extend(evidence)
        return result

    def normalize(self, raw: dict) -> Listing:
        listing_id = self._make_id(raw)
        return Listing(
            id=listing_id,
            source="yandex_market",
            url=raw.get("url", ""),
            title=raw.get("title", "Магазин без названия"),
            category=raw.get("category", "Бытовая техника"),
            description=raw.get("description"),
            seller_name=raw.get("seller_name") or raw.get("store_name"),
            price=raw.get("price"),
            city=raw.get("city"),
            phone=raw.get("phone"),
            website=raw.get("website"),
            rating=raw.get("rating"),
            reviews_count=raw.get("reviews_count"),
            images=raw.get("images", []),
            raw_data=raw,
        )

    def extract_evidence(self, listing: Listing) -> list[Evidence]:
        evidence = []

        # Название магазина — главный идентификатор на маркетплейсе
        if listing.seller_name:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_store_{self._hash(listing.seller_name)[:8]}",
                type="name_extracted",
                source_listing=listing.id,
                value=listing.seller_name,
                field="seller_name",
                strength=0.25,
                confidence=0.70,
                extraction_method="api_field",
            ))

        # Рейтинг
        if listing.rating is not None:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_rating_{self._hash(str(listing.rating))[:8]}",
                type="category_extracted",
                source_listing=listing.id,
                value=str(listing.rating),
                field="rating",
                strength=0.10,
                confidence=0.85,
                extraction_method="api_field",
            ))

        # Количество отзывов
        if listing.reviews_count is not None and listing.reviews_count > 0:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_reviews_{self._hash(str(listing.reviews_count))[:8]}",
                type="category_extracted",
                source_listing=listing.id,
                value=str(listing.reviews_count),
                field="reviews_count",
                strength=0.08,
                confidence=0.80,
                extraction_method="api_field",
            ))

        # Телефон (редко, но бывает)
        if listing.phone:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_phone_{self._hash(listing.phone)[:8]}",
                type="phone_extracted",
                source_listing=listing.id,
                value=listing.phone,
                field="phone",
                strength=0.35,
                confidence=0.85,
                extraction_method="html_parse",
            ))

        # Сайт (тоже редко)
        if listing.website:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_web_{self._hash(listing.website)[:8]}",
                type="website_extracted",
                source_listing=listing.id,
                value=listing.website,
                field="website",
                strength=0.35,
                confidence=0.85,
                extraction_method="html_parse",
            ))

        return evidence

    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            fields=["seller_name", "title", "price", "rating", "reviews_count",
                    "category", "city", "phone", "website"],
            search_modes=["by_query", "by_category", "by_store"],
            rate_limit="10/min",
            requires_proxy=False,
        )

    def limitations(self) -> ConnectorLimitations:
        return ConnectorLimitations(
            never_available=["email", "inn", "address", "working_hours"],
            sometimes_available=["phone", "website"],
            legal_restrictions=[],
        )

    @staticmethod
    def _make_id(raw: dict) -> str:
        raw_str = f"ymarket_{raw.get('url', '')}_{raw.get('seller_name', '')}"
        h = hashlib.sha256(raw_str.encode()).hexdigest()[:12]
        return f"ymk_{h}"

    @staticmethod
    def _hash(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()
