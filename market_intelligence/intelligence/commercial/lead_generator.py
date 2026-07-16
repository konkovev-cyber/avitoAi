"""Lead Generator — превращает Opportunity в коммерческие Lead'ы."""

from __future__ import annotations

import hashlib
from ..opportunity import OpportunityEngine
from ...graph.models import MarketGraph
from ...models.opportunity import Opportunity
from ...models.lead import Lead


def _hash(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:8]


LEAD_RULES = [
    {
        "id": "RULE_001",
        "name": "Digital Expansion",
        "description": "Verified seller + no website + multiple sources",
        "opportunity_types": ["no_website", "weak_digital_presence"],
        "min_opportunities": 1,
        "lead_type": "digital_expansion",
        "priority": "high",
        "action": "Предложить создание сайта / цифрового канала",
    },
    {
        "id": "RULE_002",
        "name": "Channel Diversification",
        "description": "Marketplace seller + no owned channel",
        "opportunity_types": ["marketplace_dependency", "single_source_risk"],
        "min_opportunities": 1,
        "lead_type": "channel_diversification",
        "priority": "medium",
        "action": "Проанализировать возможность выхода на другие площадки",
    },
    {
        "id": "RULE_003",
        "name": "Growth Opportunity",
        "description": "High activity + weak presence",
        "opportunity_types": ["expansion_opportunity", "competitor_gap"],
        "min_opportunities": 1,
        "lead_type": "growth_opportunity",
        "priority": "medium",
        "action": "Предложить стратегию роста / маркетинг",
    },
    {
        "id": "RULE_004",
        "name": "Local Presence Gap",
        "description": "Verified seller with phone but limited geography",
        "opportunity_types": ["multi_source_conflict"],
        "min_opportunities": 1,
        "lead_type": "local_presence_gap",
        "priority": "low",
        "action": "Проверить возможность расширения географии",
    },
]


class LeadGenerator:
    """Генерирует коммерческие Lead'ы из Market Graph + Opportunity."""

    def __init__(self):
        self.opportunity_engine = OpportunityEngine()

    def generate(self, graph: MarketGraph) -> list[Lead]:
        """Полный цикл: сканировать возможности → создать лиды."""
        # 1. Сканировать возможности
        opportunities = self.opportunity_engine.scan(graph)

        # 2. Применить правила → создать лиды
        leads = self._apply_rules(opportunities, graph)

        # 3. Рассчитать Lead Score
        from .lead_score import LeadScorer
        scorer = LeadScorer()
        for lead in leads:
            scorer.score(lead, graph)

        return leads

    def _apply_rules(self, opportunities: list[Opportunity], graph: MarketGraph) -> list[Lead]:
        """Применить LEAD_RULES к найденным возможностям."""
        leads = []

        for rule in LEAD_RULES:
            # Найти подходящие возможности
            matching = [
                o for o in opportunities
                if o.type in rule["opportunity_types"]
                and o.confidence >= 0.40  # минимальный порог
            ]

            if len(matching) < rule["min_opportunities"]:
                continue

            # Сгруппировать по entity
            by_entity: dict[str, list[Opportunity]] = {}
            for opp in matching:
                for eid in opp.entity_ids:
                    if eid not in by_entity:
                        by_entity[eid] = []
                    by_entity[eid].append(opp)

            for eid, entity_opps in by_entity.items():
                entity = graph.get_entity(eid)
                if not entity:
                    continue

                # Собрать evidence из всех подходящих возможностей
                all_evidence = []
                for opp in entity_opps:
                    for ev in opp.evidence:
                        if ev not in all_evidence:
                            all_evidence.append(ev)
                    if opp.recommendation not in all_evidence:
                        all_evidence.append(f"💡 {opp.recommendation}")

                lead_id = f"lead_{rule['lead_type']}_{_hash(eid)}"

                leads.append(Lead(
                    id=lead_id,
                    type=rule["lead_type"],
                    entity_id=eid,
                    entity_name=entity.name,
                    opportunity_ids=[o.id for o in entity_opps],
                    evidence=all_evidence,
                    rules_triggered=[rule["id"]],
                    recommended_action=rule["action"],
                    priority=rule["priority"],
                    status="new",
                ))

        return leads
