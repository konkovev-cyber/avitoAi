"""Market Graph — сущности рынка и связи между ними."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


ENTITY_TYPES = (
    "company",      # юридическое лицо (ООО, ИП, АО)
    "seller",       # продавец (частное лицо, мастер)
    "store",        # магазин на маркетплейсе
    "brand",        # бренд (Samsung, Bosch, Liebherr)
    "product",      # товар/услуга
    "location",     # точка на карте (адрес, город)
    "unknown",      # неопределённый тип
)

RELATIONSHIP_TYPES = (
    "owns",              # компания владеет магазином
    "sells",             # продавец продаёт товар/услугу
    "located_at",        # сущность находится по адресу
    "operates_as",       # компания → бренд (лицензия/франшиза)
    "same_as",           # один и тот же продавец на разных площадках
    "competes_with",     # конкуренты
    "supplies",          # поставщик
    "formerly_known_as", # ребрендинг (старое → новое название)
    "franchise",         # филиал / франчайзи
    "unknown",           # связь не определена
)


@dataclass
class GraphEntity:
    """Вершина графа — участник рынка."""

    id: str                          # entity_{type}_{hash}
    type: str                        # company | seller | store | brand | product | location
    name: str                        # лучшее известное название
    aliases: list[str] = field(default_factory=list)

    # Детали (зависят от типа)
    inn: Optional[str] = None
    ogrn: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None

    # Привязка к источнику
    source_listing_ids: list[str] = field(default_factory=list)

    # Confidence
    confidence: float = 0.0
    status: str = "hypothesis"       # hypothesis | candidate | verified

    # Мета
    evidence_ids: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, GraphEntity) and self.id == other.id

    def short(self) -> str:
        return f"[{self.type.upper()}] {self.name} (confidence={self.confidence})"


@dataclass
class Relationship:
    """Ребро графа — связь между сущностями."""

    id: str                          # rel_{type}_{from}_{to}_{hash}
    type: str                        # owns | sells | located_at | same_as | competes_with | supplies
    source_id: str                   # ID исходной сущности
    target_id: str                   # ID целевой сущности
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)  # ID evidence
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __hash__(self) -> int:
        return hash(self.id)

    def short(self) -> str:
        return f"{self.type}: {self.source_id[:16]} → {self.target_id[:16]}"


@dataclass
class MarketGraph:
    """Граф рынка: сущности + связи."""

    entities: dict[str, GraphEntity] = field(default_factory=dict)
    relationships: dict[str, Relationship] = field(default_factory=dict)

    def add_entity(self, entity: GraphEntity):
        self.entities[entity.id] = entity

    def get_entity(self, entity_id: str) -> Optional[GraphEntity]:
        return self.entities.get(entity_id)

    def add_relationship(self, rel: Relationship):
        self.relationships[rel.id] = rel

    def get_relationships(self, entity_id: str) -> list[Relationship]:
        """Все связи сущности."""
        return [
            r for r in self.relationships.values()
            if r.source_id == entity_id or r.target_id == entity_id
        ]

    def find_entity(self, name: str, entity_type: Optional[str] = None) -> list[GraphEntity]:
        """Найти сущность по имени."""
        results = []
        for e in self.entities.values():
            if name.lower() in e.name.lower() or any(name.lower() in a.lower() for a in e.aliases):
                if entity_type is None or e.type == entity_type:
                    results.append(e)
        return results

    def get_stats(self) -> dict:
        return {
            "total_entities": len(self.entities),
            "total_relationships": len(self.relationships),
            "by_type": {},
            "verified_entities": sum(1 for e in self.entities.values() if e.status == "verified"),
            "sources_connected": len(set(
                e.type for e in self.entities.values()
            )),
        }

    def merge_graphs(self, other: MarketGraph):
        """Объединить два графа."""
        for eid, entity in other.entities.items():
            if eid not in self.entities:
                self.entities[eid] = entity
        for rid, rel in other.relationships.items():
            if rid not in self.relationships:
                self.relationships[rid] = rel
