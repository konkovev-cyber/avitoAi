"""Opportunity model — гипотеза рыночной возможности на основе Evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


OPPORTUNITY_TYPES = (
    "weak_digital_presence",       # продавец без сайта/телефона
    "marketplace_dependency",      # зависимость от одной площадки
    "multi_source_conflict",       # противоречия между источниками
    "competitor_gap",              # ниша со слабой конкуренцией
    "single_source_risk",          # весь бизнес на одной площадке
    "no_phone",                    # нет телефона
    "no_website",                  # нет сайта
    "cross_source_miss",           # найден в одном, но нет в других
    "data_inconsistency",          # разные данные об одном продавце
    "expansion_opportunity",       # работает локально, есть потенциал
)

SEVERITY_LEVELS = ("critical", "high", "medium", "low", "info")


@dataclass
class Opportunity:
    """Гипотеза рыночной возможности, подкреплённая Evidence."""

    id: str                          # opp_{type}_{hash}
    type: str                        # один из OPPORTUNITY_TYPES
    severity: str = "medium"         # critical | high | medium | low | info
    confidence: float = 0.0          # 0.0-1.0

    # На какие сущности ссылается
    entity_ids: list[str] = field(default_factory=list)
    entity_names: list[str] = field(default_factory=list)

    # Доказательства
    evidence: list[str] = field(default_factory=list)  # описания причин

    # Описание
    message: str = ""
    recommendation: str = ""

    # Статус
    status: str = "candidate"        # hypothesis | candidate | validated | dismissed

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def short(self) -> str:
        return f"[{self.severity.upper()}] {self.message[:80]}"

    @property
    def is_actionable(self) -> bool:
        if self.confidence < 0.60:
            return False
        return self.severity in ("critical", "high") or (
            self.severity in ("medium",) and self.confidence >= 0.70
        )
