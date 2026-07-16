"""Graph Builder — строит Market Graph из SellerProfiles и Listing."""

from __future__ import annotations

import hashlib
from typing import Optional

from ..models.listing import Listing
from ..models.seller import SellerProfile
from ..models.evidence import Evidence
from ..resolution.matcher import EntityMatcher
from .models import GraphEntity, Relationship, MarketGraph


class GraphBuilder:
    """
    Строит Market Graph из данных.

    Pipeline:
      Listing + SellerProfile
            ↓
      Entity Resolution
            ↓
      Graph Entities
            ↓
      Relationships
            ↓
      Market Graph
    """

    def __init__(self):
        self.matcher = EntityMatcher()

    def build_from_profiles(self, profiles: list[SellerProfile],
                            listings: Optional[list[Listing]] = None) -> MarketGraph:
        """Построить граф из профилей продавцов и (опционально) Listing."""
        graph = MarketGraph()

        for profile in profiles:
            entity = self._profile_to_entity(profile)
            graph.add_entity(entity)

        # Добавить Listing как product-entity, если есть
        if listings:
            for listing in listings:
                product = self._listing_to_product(listing)
                if product:
                    graph.add_entity(product)
                    # Связать product с seller
                    for pid, entity in graph.entities.items():
                        if entity.type in ("seller", "store", "company"):
                            rel = Relationship(
                                id=f"rel_sells_{entity.id[:8]}_{product.id[:8]}",
                                type="sells",
                                source_id=entity.id,
                                target_id=product.id,
                                confidence=0.50,
                            )
                            graph.add_relationship(rel)

        # Построить same_as-связи между похожими профилями
        self._link_profiles(graph, profiles)

        return graph

    def _profile_to_entity(self, profile: SellerProfile) -> GraphEntity:
        """SellerProfile → GraphEntity."""
        # Определить тип сущности
        entity_type = self._infer_entity_type(profile)

        entity_id = f"entity_{entity_type}_{hashlib.md5(profile.name.encode()).hexdigest()[:8]}"

        return GraphEntity(
            id=entity_id,
            type=entity_type,
            name=profile.name,
            aliases=[],
            inn=profile.inn,
            phone=profile.phones[0] if profile.phones else None,
            email=profile.emails[0] if profile.emails else None,
            website=profile.websites[0] if profile.websites else None,
            city=profile.addresses[0] if profile.addresses else None,
            source_listing_ids=profile.listing_ids,
            confidence=profile.confidence,
            status=profile.status,
            evidence_ids=profile.evidence_ids,
        )

    def _listing_to_product(self, listing: Listing) -> Optional[GraphEntity]:
        """Listing → product entity (если есть цена и название)."""
        if not listing.title or listing.title == "Без названия":
            return None

        entity_id = f"entity_product_{hashlib.md5(listing.id.encode()).hexdigest()[:8]}"

        return GraphEntity(
            id=entity_id,
            type="product",
            name=listing.title[:100],
            source_listing_ids=[listing.id],
            city=listing.city,
            confidence=0.80,
            status="verified",
        )

    def _link_profiles(self, graph: MarketGraph, profiles: list[SellerProfile]):
        """Найти same_as-связи между профилями."""
        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                a_id = f"entity_{self._infer_entity_type(profiles[i])}_{hashlib.md5(profiles[i].name.encode()).hexdigest()[:8]}"
                b_id = f"entity_{self._infer_entity_type(profiles[j])}_{hashlib.md5(profiles[j].name.encode()).hexdigest()[:8]}"

                # Проверяем по матчеру
                match = self.matcher.compare_profiles(profiles[i], profiles[j])

                if match.confidence >= 0.30:
                    rel_type = "same_as" if match.confidence >= 0.60 else "unknown"
                    rel_id_hash = hashlib.md5(f"{a_id}_{b_id}".encode()).hexdigest()[:12]
                    rel = Relationship(
                        id=f"rel_{rel_type}_{rel_id_hash}",
                        type=rel_type,
                        source_id=a_id,
                        target_id=b_id,
                        confidence=match.confidence,
                        evidence=[s["type"] for s in match.signals],
                        metadata={
                            "signals": match.signals,
                            "negative_signals": match.negative_signals,
                        },
                    )
                    graph.add_relationship(rel)

    @staticmethod
    def _infer_entity_type(profile: SellerProfile) -> str:
        """Определить тип сущности по данным профиля."""
        if profile.inn:
            return "company"
        if any(src in ["yandex_market", "ozon", "wildberries"] for src in profile.source_names):
            return "store"
        if any(src in ["avito", "youla"] for src in profile.source_names):
            return "seller"
        if profile.source_names and len(profile.source_names) > 1:
            return "company"
        return "seller"

    @staticmethod
    def report(graph: MarketGraph) -> str:
        """Сформировать текстовый отчёт по графу."""
        stats = graph.get_stats()
        lines = [
            "📊 Market Graph Report",
            f"  Entities: {stats['total_entities']}",
            f"  Relationships: {stats['total_relationships']}",
            f"  Verified: {stats['verified_entities']}",
            f"  Source types: {stats['sources_connected']}",
            "",
            "Entities by type:",
        ]
        for e in graph.entities.values():
            rels = graph.get_relationships(e.id)
            lines.append(f"  [{e.status.upper()}] {e.short()} — {len(rels)} связей")

        return "\n".join(lines)
