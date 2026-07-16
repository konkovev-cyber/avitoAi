"""Yandex Maps Connector — первый production коннектор."""

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


class YandexMapsConnector(BaseConnector):
    """Connector для Яндекс Карт. Работает с уже собранным HTML."""

    def __init__(self):
        super().__init__()
        self.name = "yandex_maps"

    def collect(self, query: str, html: Optional[str] = None, **kwargs) -> ConnectorResult:
        """
        Основной метод.
        Принимает HTML-выдачу Яндекс Карт, возвращает Listing + Evidence.

        Если html не передан — использует тестовые данные из kwargs.
        """
        if html is None and "test_data" in kwargs:
            html = kwargs["test_data"]
        if not html:
            return ConnectorResult()

        items = self._parse_items(html)
        result = ConnectorResult()

        for item in items:
            listing = self.normalize(item)
            evidence = self.extract_evidence(listing)
            result.listings.append(listing)
            result.evidence.extend(evidence)

        return result

    def normalize(self, raw: dict) -> Listing:
        """Преобразовать сырой элемент с карты в Listing."""
        listing_id = self._make_id(raw)
        return Listing(
            id=listing_id,
            source="yandex_maps",
            url=raw.get("url", ""),
            title=raw.get("title", "Без названия"),
            category=raw.get("category", "Ремонт бытовой техники"),
            seller_name=raw.get("seller_name"),
            city=raw.get("city"),
            address=raw.get("address"),
            phone=raw.get("phone"),
            website=raw.get("website"),
            rating=raw.get("rating"),
            reviews_count=raw.get("reviews_count"),
            working_hours=raw.get("working_hours"),
            description=raw.get("description"),
            images=raw.get("images", []),
            price=raw.get("price"),
            raw_data=raw,
        )

    def extract_evidence(self, listing: Listing) -> list[Evidence]:
        """Извлечь Evidence из Listing."""
        evidence = []

        if listing.phone:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_phone_{self._hash(listing.phone)[:8]}",
                type="phone_extracted",
                source_listing=listing.id,
                value=listing.phone,
                field="phone",
                strength=0.35,
                extraction_method="html_parse",
            ))

        if listing.website:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_web_{self._hash(listing.website)[:8]}",
                type="website_extracted",
                source_listing=listing.id,
                value=listing.website,
                field="website",
                strength=0.30,
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
                extraction_method="html_parse",
            ))

        if listing.email:
            evidence.append(Evidence(
                id=f"ev_{listing.id}_email_{self._hash(listing.email)[:8]}",
                type="email_extracted",
                source_listing=listing.id,
                value=listing.email,
                field="email",
                strength=0.30,
                extraction_method="html_parse",
            ))

        return evidence

    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            fields=["title", "category", "seller_name", "address", "city", "rating",
                    "reviews_count", "working_hours", "website", "phone"],
            search_modes=["by_query", "by_category"],
            rate_limit="30/min",
            requires_proxy=False,
        )

    def limitations(self) -> ConnectorLimitations:
        return ConnectorLimitations(
            never_available=["email", "inn"],
            sometimes_available=["phone", "website"],
            legal_restrictions=[],
        )

    # ── Parser ─────────────────────────────────────────────────────────────

    def _parse_items(self, html: str) -> list[dict]:
        """Парсинг HTML-выдачи Яндекс Карт."""
        items = []

        # Разделяем по маркерам организаций
        # Яндекс Карты использует структуру: Название + Рейтинг + Адрес
        blocks = self._split_blocks(html)

        for block in blocks:
            item = self._parse_block(block)
            if item and item.get("title"):
                items.append(item)

        return items

    def _split_blocks(self, html: str) -> list[str]:
        """Разделить HTML на блоки организаций."""
        # Ищем начало блока: либо название сразу после рейтинга
        # Яндекс Карты: каждая организация отделена маркерами
        blocks = []

        # Простой split по "Фото" (маркер карточки в выдаче)
        # Более надёжно: ищем повторяющиеся паттерны
        parts = re.split(r'(?=Рейтинг\s*\d)', html)
        for part in parts:
            part = part.strip()
            if part and len(part) > 50:  # минимум контента
                blocks.append(part)

        return blocks if blocks else [html]

    def _parse_block(self, block: str) -> Optional[dict]:
        """Извлечь данные из блока одной организации."""
        item = {}
        item["url"] = self._extract_url(block)
        item["title"] = self._extract_title(block)
        item["rating"] = self._extract_rating(block)
        item["reviews_count"] = self._extract_reviews(block)
        item["address"] = self._extract_address(block)
        item["city"] = self._extract_city(block)
        item["category"] = self._extract_category(block)
        item["working_hours"] = self._extract_hours(block)
        item["website"] = self._extract_website(block)
        item["phone"] = self._extract_phone(block)
        item["price"] = self._extract_price(block)
        item["description"] = self._extract_description(block)

        if not item["title"]:
            return None

        # Нормализовать название
        item["seller_name"] = item["title"]
        item["images"] = []

        return item

    # ── Extraction helpers ─────────────────────────────────────────────────

    @staticmethod
    def _extract_title(block: str) -> Optional[str]:
        # Ищем название: часто после маркера организации
        patterns = [
            r'Сервисный центр\s+([A-Za-zА-Яа-я\s]+)',
            r'Ремонт\s+[\w\s]+\n(.+?)(?:\n|Рейтинг)',
            r'(?:Фото\n)(.+?)(?:\n|Рейтинг)',
        ]
        for p in patterns:
            m = re.search(p, block)
            if m:
                name = m.group(1).strip()
                if name and len(name) > 1:
                    return name[:100]
        return None

    @staticmethod
    def _extract_url(block: str) -> str:
        m = re.search(r'(org/[a-zA-Z0-9_]+)', block)
        if m:
            return f"https://yandex.ru/maps/{m.group(1)}"
        return ""

    @staticmethod
    def _extract_rating(block: str) -> Optional[float]:
        m = re.search(r'Рейтинг\s*[×x]?\s*(\d[\d.]*)', block)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
        return None

    @staticmethod
    def _extract_reviews(block: str) -> Optional[int]:
        # Количество оценок: "(123)" или "123 оценки"
        m = re.search(r'(\d+)\s*(?:оценк|отзыв)', block)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _extract_address(block: str) -> Optional[str]:
        # Адрес — строка после рейтинга/часов работы
        m = re.search(r'(?:до\s*\d+:\d+|работает)\s*\n(.{10,80})', block)
        if m:
            addr = m.group(1).strip()
            if not any(kw in addr for kw in ['Ремонт', 'Акция', 'Подборка', 'В подборке', 'Хорошее']):
                return addr[:100]
        return None

    @staticmethod
    def _extract_city(block: str) -> Optional[str]:
        if 'Москв' in block:
            return "Москва"
        for city in ['Жуковский', 'Щёлково', 'Лыткарино', 'Домодедово']:
            if city in block:
                return city
        return None

    @staticmethod
    def _extract_category(block: str) -> str:
        m = re.search(r'(Ремонт[\w\s]+)', block)
        if m:
            return m.group(1).strip()
        return "Ремонт бытовой техники"

    @staticmethod
    def _extract_hours(block: str) -> Optional[str]:
        m = re.search(r'(?:Открыто|работает)\s*(?:до|c)\s*(\d+:\d+)', block)
        if m:
            return f"до {m.group(1)}"
        return None

    @staticmethod
    def _extract_website(block: str) -> Optional[str]:
        m = re.search(r'([\w\-]+\.(?:ru|com|рф))', block)
        if m:
            domain = m.group(1)
            # Исключить общие домены
            if domain not in ('yandex.ru', 'yandex.com', 'google.com'):
                return domain
        return None

    @staticmethod
    def _extract_phone(block: str) -> Optional[str]:
        m = re.search(r'\+7[\s\-\(\)\d]{10,15}', block)
        if m:
            return m.group(0).strip()
        return None

    @staticmethod
    def _extract_price(block: str) -> Optional[float]:
        m = re.search(r'(\d[\d\s]*)\s*₽', block)
        if m:
            try:
                return float(m.group(1).replace(" ", ""))
            except ValueError:
                pass
        return None

    @staticmethod
    def _extract_description(block: str) -> Optional[str]:
        m = re.search(r'(?:В подборке|Акция):\s*(.+?)(?:\n|$)', block)
        if m:
            return m.group(1).strip()[:200]
        return None

    @staticmethod
    def _make_id(raw: dict) -> str:
        raw_str = f"{raw.get('title', '')}_{raw.get('address', '')}_{raw.get('phone', '')}"
        h = hashlib.sha256(raw_str.encode()).hexdigest()[:12]
        return f"ym_{h}"

    @staticmethod
    def _hash(s: str) -> str:
        return hashlib.sha256(s.encode()).hexdigest()
