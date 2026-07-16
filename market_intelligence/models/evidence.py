"""Evidence model — атомарное доказательство."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


EVIDENCE_TYPES = (
    "phone_extracted",
    "email_extracted",
    "address_extracted",
    "website_extracted",
    "inn_extracted",
    "ogrn_extracted",
    "name_extracted",
    "category_extracted",
    "photo_hash",
    "working_hours",
    "cross_source_address_match",
    "cross_source_website_match",
    "cross_source_phone_match",
    "negative_match",
)


@dataclass
class Evidence:
    """Атомарное доказательство — извлечённый признак из Listing."""

    id: str                          # source_type_hash
    type: str                        # один из EVIDENCE_TYPES
    source_listing: str              # ID listing, откуда извлечено
    value: str                       # значение признака
    field: str                       # поле в listing
    strength: float = 0.0            # 0.0-1.0 — вклад в решение
    confidence: float = 0.9          # насколько уверены в правильности
    extraction_method: str = "rule_based"  # rule_based | html_parse | api_field | ai
    collection_date: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self):
        if self.type not in EVIDENCE_TYPES:
            raise ValueError(f"Unknown evidence type: {self.type}")

    def short(self) -> str:
        return f"[{self.type}] {self.value[:40]} (strength={self.strength})"
