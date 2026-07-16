"""Scorer — метрики продавцов и рынка из Market Graph."""

from __future__ import annotations

from ..graph.models import MarketGraph, GraphEntity

# Маппинг префиксов source_listing_id → ключ веса
SOURCE_PREFIX_MAP = {
    "ym": "yandex_maps",
    "yandex": "yandex_maps",
    "av": "avito",
    "avito": "avito",
    "site": "company_website",
    "ymk": "yandex_market",
    "oz": "ozon",
    "wb": "wildberries",
}

# Веса для Visibility Score
WEIGHTS = {
    "source_yandex_maps": 15,
    "source_company_website": 25,
    "source_avito": 10,
    "source_youla": 8,
    "source_yandex_market": 15,
    "source_ozon": 15,
    "source_wildberries": 12,
    "has_phone": 15,
    "has_email": 10,
    "has_inn": 20,
    "has_website": 25,
    "evidence_per_point": 2,   # за каждое evidence
    "relationship_per_point": 3,  # за каждую связь
}


class SellerScorer:
    """Оценка видимости и качества профиля продавца."""

    def visibility_score(self, entity: GraphEntity, graph: MarketGraph) -> dict:
        """Рассчитать Visibility Score для одной сущности."""
        score = 0
        breakdown = {}

        # 1. Источники (по префиксам listing_id)
        seen_sources = set()
        for src in entity.source_listing_ids:
            prefix = src.split("_")[0] if "_" in src else src
            src_name = SOURCE_PREFIX_MAP.get(prefix, prefix)
            if src_name not in seen_sources:
                seen_sources.add(src_name)
                key = f"source_{src_name}"
                if key in WEIGHTS:
                    score += WEIGHTS[key]
                    breakdown[key] = WEIGHTS[key]

        # 2. Контакты
        if entity.phone:
            score += WEIGHTS["has_phone"]
            breakdown["has_phone"] = WEIGHTS["has_phone"]
        if entity.email:
            score += WEIGHTS["has_email"]
            breakdown["has_email"] = WEIGHTS["has_email"]
        if entity.inn:
            score += WEIGHTS["has_inn"]
            breakdown["has_inn"] = WEIGHTS["has_inn"]
        if entity.website:
            score += WEIGHTS["has_website"]
            breakdown["has_website"] = WEIGHTS["has_website"]

        # 3. Evidence
        ev_score = len(entity.evidence_ids) * WEIGHTS["evidence_per_point"]
        if ev_score:
            score += ev_score
            breakdown["evidence"] = ev_score

        # 4. Relationships
        rels = graph.get_relationships(entity.id)
        rel_score = len(rels) * WEIGHTS["relationship_per_point"]
        if rel_score:
            score += rel_score
            breakdown["relationships"] = rel_score

        return {
            "entity_id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "status": entity.status,
            "total_score": min(score, 100),
            "breakdown": breakdown,
            "source_count": len(seen_sources),
            "evidence_count": len(entity.evidence_ids),
            "relationship_count": len(rels),
        }

    def visibility_rank(self, results: list[dict]) -> list[dict]:
        """Отсортировать по убыванию Visibility Score."""
        return sorted(results, key=lambda r: r["total_score"], reverse=True)

    def top_players(self, results: list[dict], n: int = 5) -> list[dict]:
        """Топ-N продавцов на рынке."""
        return self.visibility_rank(results)[:n]


class MarketScorer:
    """Оценка рынка в целом."""

    def market_summary(self, graph: MarketGraph) -> dict:
        """Общая статистика рынка."""
        entities = list(graph.entities.values())
        rels = list(graph.relationships.values())

        by_type = {}
        for e in entities:
            by_type[e.type] = by_type.get(e.type, 0) + 1

        verified = [e for e in entities if e.status == "verified"]
        with_phone = [e for e in entities if e.phone]
        with_website = [e for e in entities if e.website]
        with_inn = [e for e in entities if e.inn]

        return {
            "total_entities": len(entities),
            "total_relationships": len(rels),
            "by_type": by_type,
            "verified": len(verified),
            "with_phone": len(with_phone),
            "with_website": len(with_website),
            "with_inn": len(with_inn),
            "sources_used": len(set(
                SOURCE_PREFIX_MAP.get(s.split("_")[0], s.split("_")[0])
                for e in entities for s in e.source_listing_ids
            )),
        }

    def opportunity_signals(self, graph: MarketGraph) -> list[dict]:
        """Найти потенциальные возможности."""
        signals = []
        entities = list(graph.entities.values())

        # Signal 001: Seller exists but has no website
        no_website = [e for e in entities if not e.website and e.status in ("verified", "candidate")]
        if no_website:
            signals.append({
                "type": "missing_website",
                "severity": "high",
                "count": len(no_website),
                "examples": [e.name for e in no_website[:3]],
                "message": f"{len(no_website)} продавцов без сайта",
                "opportunity": "создание/продвижение сайта",
            })

        # Signal 002: Seller exists but has no phone
        no_phone = [e for e in entities if not e.phone and e.status == "verified"]
        if no_phone:
            signals.append({
                "type": "missing_phone",
                "severity": "medium",
                "count": len(no_phone),
                "examples": [e.name for e in no_phone[:3]],
                "message": f"{len(no_phone)} продавцов без телефона",
                "opportunity": "CRM/телефония",
            })

        # Signal 003: Single-source sellers
        single_source = [e for e in entities if len(e.source_listing_ids) == 1]
        if single_source:
            signals.append({
                "type": "single_source",
                "severity": "medium",
                "count": len(single_source),
                "examples": [e.name for e in single_source[:3]],
                "message": f"{len(single_source)} продавцов только в одном источнике",
                "opportunity": "расширение присутствия на других площадках",
            })

        # Signal 004: High visibility gap
        verified_list = [e for e in entities if e.status == "verified" and e.source_listing_ids]
        low_vis = [e for e in verified_list if len(e.source_listing_ids) <= 2]
        if low_vis:
            signals.append({
                "type": "low_visibility",
                "severity": "low",
                "count": len(low_vis),
                "examples": [e.name for e in low_vis[:3]],
                "message": f"{len(low_vis)} верифицированных продавцов имеют слабую представленность",
                "opportunity": "SEO / маркетинг",
            })

        return signals
