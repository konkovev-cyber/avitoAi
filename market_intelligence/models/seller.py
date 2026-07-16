"""Seller Profile model — результат Entity Resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SellerProfile:
    """Профиль продавца — результат объединения evidence из разных источников."""

    id: str                          # seller_{uuid}
    name: str                        # лучшее известное название
    confidence: float = 0.0          # 0.0-1.0
    status: str = "hypothesis"       # hypothesis | candidate | strong | verified

    # Агрегированные данные
    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    websites: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    inn: Optional[str] = None
    ogrn: Optional[str] = None

    # Источники
    listing_ids: list[str] = field(default_factory=list)
    source_names: list[str] = field(default_factory=list)

    # Доказательства
    evidence_ids: list[str] = field(default_factory=list)

    # Мета
    evidence_density: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: str = ""

    @property
    def is_verified(self) -> bool:
        return self.status == "verified"

    @property
    def is_cross_source(self) -> bool:
        return len(set(self.source_names)) > 1

    def summary(self) -> str:
        src = ", ".join(sorted(set(self.source_names)))
        return (
            f"[{self.status.upper()}] {self.name} "
            f"(confidence={self.confidence:.2f}, "
            f"evidence={self.evidence_density}, "
            f"sources=[{src}])"
        )


@dataclass
class MatchHypothesis:
    """Гипотеза о том, что два listing/профиля принадлежат одному продавцу."""

    id: str
    entity_a_id: str
    entity_b_id: str
    confidence: float
    signals: list[dict] = field(default_factory=list)  # [{"type": "phone", "weight": 0.35, "value": "..."}]
    negative_signals: list[dict] = field(default_factory=list)
    decision: str = "unknown"       # unknown | candidate | strong_match | verified | different
    requires_review: bool = True
    explanation: str = ""
