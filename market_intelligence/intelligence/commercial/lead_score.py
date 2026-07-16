"""Lead Score — вычисление и объяснение score для Lead."""

from __future__ import annotations

from ...models.lead import Lead
from ...graph.models import MarketGraph


class LeadScorer:
    """Вычисляет объяснимый Score для Lead на основе данных графа."""

    def score(self, lead: Lead, graph: MarketGraph) -> Lead:
        """Рассчитать score 0-100 с разложением по компонентам."""
        score = 0
        breakdown = []

        entity = graph.get_entity(lead.entity_id)

        # 1. Статус верификации (0-20)
        if entity and entity.status == "verified":
            score += 20
            breakdown.append({"component": "verified_entity", "weight": 20, "reason": "Продавец верифицирован"})
        elif entity and entity.status == "candidate":
            score += 10
            breakdown.append({"component": "candidate_entity", "weight": 10, "reason": "Продавец кандидат"})

        # 2. Количество evidence (0-20)
        if entity and entity.evidence_ids:
            ev_count = len(entity.evidence_ids)
            ev_score = min(ev_count * 4, 20)
            score += ev_score
            breakdown.append({"component": "evidence_count", "weight": ev_score, "reason": f"{ev_count} доказательств"})

        # 3. Количество источников (0-20)
        if entity and entity.source_listing_ids:
            src_count = len(set(s.split("_")[0] for s in entity.source_listing_ids if "_" in s))
            src_score = min(src_count * 5, 20)
            score += src_score
            breakdown.append({"component": "source_diversity", "weight": src_score, "reason": f"{src_count} источников"})

        # 4. Наличие контактов (0-15)
        contact_score = 0
        if entity and entity.phone:
            contact_score += 8
        if entity and entity.website:
            contact_score += 7
        score += contact_score
        if contact_score:
            breakdown.append({"component": "contact_availability", "weight": contact_score, "reason": "Есть контакты"})

        # 5. Количество возможностей (0-15)
        opp_count = len(lead.opportunity_ids)
        opp_score = min(opp_count * 5, 15)
        score += opp_score
        if opp_count:
            breakdown.append({"component": "opportunity_count", "weight": opp_score, "reason": f"{opp_count} возможностей"})

        # 6. Приоритет (0-10)
        priority_map = {"high": 10, "medium": 6, "low": 3}
        priority_score = priority_map.get(lead.priority, 5)
        score += priority_score
        breakdown.append({"component": "priority", "weight": priority_score, "reason": f"Приоритет {lead.priority}"})

        # Бонус: Evidence в графе (0-10)
        if entity:
            rels = graph.get_relationships(entity.id)
            rel_score = min(len(rels) * 3, 10)
            if rel_score:
                score += rel_score
                breakdown.append({"component": "graph_relationships", "weight": rel_score, "reason": f"{len(rels)} связей"})

        lead.score = min(score, 100)
        lead.score_breakdown = breakdown

        return lead

    @staticmethod
    def explain(lead: Lead) -> str:
        """Сформировать человекочитаемое объяснение score."""
        lines = [
            f"📊 Lead Score: {lead.score}/100",
            f"  Тип: {lead.type}",
            f"  Продавец: {lead.entity_name}",
            f"  Приоритет: {lead.priority}",
            "",
            "  Разложение score:",
        ]
        for item in lead.score_breakdown:
            lines.append(f"    +{item['weight']} {item['reason']}")

        lines.extend([
            "",
            f"  Evidence ({len(lead.evidence)}):",
        ])
        for ev in lead.evidence:
            lines.append(f"    → {ev}")

        lines.extend([
            "",
            f"  Рекомендация: {lead.recommended_action}",
        ])

        return "\n".join(lines)
