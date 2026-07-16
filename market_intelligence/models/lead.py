"""Lead model — коммерческая возможность на основе Market Graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


LEAD_TYPES = (
    "digital_expansion",           # компания без сайта
    "channel_diversification",     # зависимость от одной площадки
    "growth_opportunity",          # высокая активность + слабое присутствие
    "marketplace_optimization",    # продавец на маркетплейсе без оптимизации
    "local_presence_gap",          # есть в одном регионе, нет в других
)

LEAD_STATUSES = ("new", "reviewing", "qualified", "rejected", "archived")


@dataclass
class Lead:
    """Коммерческая возможность — рекомендация на основе интеллекта рынка."""

    id: str                          # lead_{type}_{hash}
    type: str                        # один из LEAD_TYPES
    score: float = 0.0               # 0-100
    score_breakdown: list[dict] = field(default_factory=list)  # почему такой score

    # Ссылки на граф и evidence
    entity_id: str = ""
    entity_name: str = ""
    opportunity_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)  # человекочитаемые причины
    rules_triggered: list[str] = field(default_factory=list)

    # Статус
    status: str = "new"              # new | reviewing | qualified | rejected

    # Рекомендация
    recommended_action: str = ""
    priority: str = "medium"         # high | medium | low

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def short(self) -> str:
        return f"[{self.score}/100] {self.type}: {self.entity_name}"

    @property
    def is_actionable(self) -> bool:
        return self.score >= 60 and self.status == "new"

    @property
    def has_evidence(self) -> bool:
        return len(self.evidence) >= 1
