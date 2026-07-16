"""Listing model — единая модель данных для всех коннекторов."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Listing:
    """Нормализованное представление объявления/карточки из любого источника."""

    # Обязательные поля
    id: str                          # source_listing_{hash}
    source: str                      # yandex_maps | company_website | avito | ...
    url: str                         # прямая ссылка
    title: str                       # название
    category: str                    # "Ремонт бытовой техники / Ремонт холодильников"
    collection_date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Опциональные
    description: Optional[str] = None
    price: Optional[float] = None
    currency: str = "RUB"
    seller_name: Optional[str] = None
    raw_data: dict = field(default_factory=dict)

    # Контакты
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    telegram: Optional[str] = None

    # Локация
    city: Optional[str] = None
    address: Optional[str] = None
    coordinates: Optional[dict] = None  # {"lat": ..., "lng": ...}

    # Медиа
    images: list[str] = field(default_factory=list)
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    working_hours: Optional[str] = None

    # Мета
    connector_version: str = "1.0"

    def short(self) -> str:
        return f"[{self.source}] {self.title[:50]} — {self.price or 'б/ц'} ₽"

    def has_phone(self) -> bool:
        return bool(self.phone)

    def has_website(self) -> bool:
        return bool(self.website)

    def has_email(self) -> bool:
        return bool(self.email)

    def contact_score(self) -> int:
        """Сколько контактных данных доступно (0-3)."""
        return sum([bool(self.phone), bool(self.email), bool(self.website)])
