"""Avito Connector — грязные данные, частники, хаос."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

from ..models.listing import Listing
from ..models.evidence import Evidence
from .base import (
    BaseConnector,
    ConnectorResult,
    ConnectorCapabilities,
    ConnectorLimitations,
    ConnectorHealth,
)


class AvitoConnector(BaseConnector):
    """
    Connector для Avito.ru.

    Avito — самый сложный источник:
    - CAPTCHA при автоматическом сборе
    - Телефоны часто скрыты за кнопкой «Показать»
    - Минимум структурированных данных
    - Максимум частных продавцов (False Merge risk)
    """

    def __init__(self):
        super().__init__()
        self.name = "avito"

    def collect(self, query: str, test_data: Optional[list[dict]] = None, **kwargs) -> ConnectorResult:
        """
        Собрать данные из Avito.

        В production использует Playwright (см. collector/avito.py).
        Для тестов принимает test_data — список словарей с данными объявлений.
        """
        if test_data is not None:
            return self._collect_from_test_data(test_data)

        # В реальном режиме — вызов Playwright
        # Пока заглушка
        return ConnectorResult()

    def _collect_from_test_data(self, items: list[dict]) -> ConnectorResult:
        """Преобразовать тестовые данные в ConnectorResult."""
        result = ConnectorResult()

        for item in items:
            listing = self.normalize(item)
            evidence = self.extract_evidence(listing)
            result.listings.append(listing)
            result.evidence.extend(evidence)

        return result

    def normalize(self, raw: dict) -> Listing:
        """Преобразовать сырые данные Avito в единый Listing."""
        listing_id = self._make_id(raw)

        return Listing(
            id=listing_id,
            source="avito",
            url=raw.get("url", ""),
            title=raw.get("title", "Без названия"),
            category=raw.get("category", "Ремонт бытовой техники"),
            description=raw.get("description"),
            seller_name=raw.get("seller_name"),
            price=raw.get("price"),
            city=raw.get("city"),
            address=raw.get("address"),
            phone=raw.get("phone"),
            website=raw.get("website"),
            images=raw.get("images", []),
            rating=raw.get("rating"),
            reviews_count=raw.get("reviews_count"),
            working_hours=raw.get("working_hours"),
            raw_data=raw,
        )

    def extract_evidence(self, listing: Listing) -> list[Evidence]:
        """Извлечь Evidence из Avito Listing."""
        evidence = []

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

        if listing.seller_name and listing.seller_name not in ("", "Неизвестно"):
            evidence.append(Evidence(
                id=f"ev_{listing.id}_name_{self._hash(listing.seller_name)[:8]}",
                type="name_extracted",
                source_listing=listing.id,
                value=listing.seller_name,
                field="seller_name",
                strength=0.08,
                confidence=0.60,
                extraction_method="html_parse",
            ))

        if listing.address:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_addr_{self._hash(listing.address)[:8]}",
                type="address_extracted",
                source_listing=listing.id,
                value=listing.address,
                field="address",
                strength=0.25,
                confidence=0.70,
                extraction_method="html_parse",
            ))

        if listing.price and listing.price > 0:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_price_{self._hash(str(listing.price))[:8]}",
                type="category_extracted",
                source_listing=listing.id,
                value=str(listing.price),
                field="price",
                strength=0.05,
                confidence=0.95,
                extraction_method="html_parse",
            ))

        if listing.description:
            # Извлечь телефон из описания, если не указан отдельно
            phone_in_desc = self._find_phone_in_text(listing.description)
            if phone_in_desc and not listing.phone:
                evidence.append(Evidence(
                    id=f"ev_{listing.id}_phone_desc_{self._hash(phone_in_desc)[:8]}",
                    type="phone_extracted",
                    source_listing=listing.id,
                    value=phone_in_desc,
                    field="description",
                    strength=0.30,  # чуть ниже, чем явный телефон
                    confidence=0.70,
                    extraction_method="rule_based",
                ))

        return evidence

    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            fields=["title", "description", "price", "category", "seller_name",
                    "phone", "address", "city", "images"],
            search_modes=["by_query", "by_category", "by_url"],
            rate_limit="5/min",
            requires_proxy=True,
        )

    def limitations(self) -> ConnectorLimitations:
        return ConnectorLimitations(
            never_available=["email", "website", "inn", "working_hours"],
            sometimes_available=["phone", "seller_name", "description"],
            legal_restrictions=["TOS Avito запрещает автоматический сбор"],
        )

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _find_phone_in_text(text: str) -> Optional[str]:
        """Найти телефон в тексте (описание, комментарий)."""
        # Более надёжный паттерн: +7/NNN/NN/NN/NN с любыми разделителями
        patterns = [
            r'\+7[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d',
            r'8[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d[\s\-\(\)]*\d',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(0).strip()
        return None

    @staticmethod
    def _find_name_in_text(text: str) -> Optional[str]:
        """Найти имя/название в тексте."""
        # Ищем обращения: зовут Сергей, мастер Иван и т.д.
        patterns = [
            r'(?:зовут|меня|мастер|обращаться)\s+([А-Я][а-я]+)',
            r'([А-Я][а-я]+)\s+(?:ИП|ООО)',
        ]
        for p in patterns:
            m = re.search(p, text)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def _make_id(raw: dict) -> str:
        raw_str = f"avito_{raw.get('url', '')}_{raw.get('title', '')}"
        h = hashlib.sha256(raw_str.encode()).hexdigest()[:12]
        return f"av_{h}"

    @staticmethod
    def _hash(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()
