"""Offer model — наблюдение с маркетплейса (продавец, товар, цена, бренд).

Отличие от Listing:
  - Listing = объявление (Avito, Yandex Maps)
  - Offer  = товарное предложение (Ozon, Yandex Market, Wildberries)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Offer:
    """Товарное предложение с маркетплейса."""

    # Обязательные поля
    id: str                          # oz_{hash}
    source: str                      # ozon | yandex_market | wildberries
    url: str                         # прямая ссылка на offer
    title: str                       # название товара
    collection_date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Продавец (главный идентификатор на маркетплейсе)
    seller_name: str = ""            # название магазина на площадке
    seller_url: str = ""             # ссылка на магазин на площадке

    # Товар
    sku: str = ""                    # артикул / SKU
    brand: str = ""                  # бренд (Samsung, Bosch, ...)
    category: str = ""               # категория товара
    price: Optional[float] = None
    currency: str = "RUB"
    description: str = ""

    # Рейтинг
    rating: Optional[float] = None
    reviews_count: Optional[int] = None

    # Контакты (редко доступны на маркетплейсе напрямую)
    phone: Optional[str] = None
    website: Optional[str] = None

    # Медиа
    images: list[str] = field(default_factory=list)

    # Мета
    raw_data: dict = field(default_factory=dict)
    connector_version: str = "1.0"

    def short(self) -> str:
        store = self.seller_name or "?"
        return f"[{self.source}] {store}: {self.title[:40]} — {self.price or 'б/ц'}₽"

    @property
    def has_sku(self) -> bool:
        return bool(self.sku)

    @property
    def has_brand(self) -> bool:
        return bool(self.brand)

    @property
    def contact_score(self) -> int:
        """Сколько контактных данных доступно (0-2)."""
        return sum([bool(self.phone), bool(self.website)])

    def to_listing(self):
        """Преобразовать Offer в Listing для Pipeline."""
        from .listing import Listing
        return Listing(
            id=self.id,
            source=self.source,
            url=self.url,
            title=self.title,
            category=self.category,
            description=self.description,
            seller_name=self.seller_name,
            price=self.price,
            phone=self.phone,
            website=self.website,
            rating=self.rating,
            reviews_count=self.reviews_count,
            images=self.images,
            raw_data=self.raw_data,
        )
