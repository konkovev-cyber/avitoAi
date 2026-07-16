"""BaseConnector — контракт для всех коннекторов."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional

from ..models.listing import Listing
from ..models.evidence import Evidence


@dataclass
class ConnectorResult:
    """Единственное, что возвращает коннектор: Listing + Evidence."""
    listings: list[Listing] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class ConnectorHealth:
    status: str = "healthy"          # healthy | degraded | down
    last_success: Optional[str] = None
    error: Optional[str] = None
    response_time_ms: int = 0


@dataclass
class ConnectorCapabilities:
    """Какие поля коннектор умеет заполнять."""
    fields: list[str] = field(default_factory=list)
    search_modes: list[str] = field(default_factory=lambda: ["by_query"])
    rate_limit: str = "30/min"
    requires_proxy: bool = False


@dataclass
class ConnectorLimitations:
    """Какие поля коннектор НЕ может заполнить."""
    never_available: list[str] = field(default_factory=list)
    sometimes_available: list[str] = field(default_factory=list)
    legal_restrictions: list[str] = field(default_factory=list)


class BaseConnector(abc.ABC):
    """Абстрактный коннектор. Все коннекторы наследуются от него."""

    def __init__(self):
        self.name = self.__class__.__name__.replace("Connector", "").lower()

    @abc.abstractmethod
    def collect(self, query: str, **kwargs) -> ConnectorResult:
        """Собрать данные из источника. Вернуть Listing + Evidence."""
        ...

    @abc.abstractmethod
    def normalize(self, raw: dict) -> Listing:
        """Преобразовать сырые данные в единый Listing."""
        ...

    @abc.abstractmethod
    def extract_evidence(self, item: Listing) -> list[Evidence]:
        """Извлечь Evidence из Listing (до того, как он попадёт в ER)."""
        ...

    def health(self) -> ConnectorHealth:
        return ConnectorHealth(status="healthy")

    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities()

    def limitations(self) -> ConnectorLimitations:
        return ConnectorLimitations()
