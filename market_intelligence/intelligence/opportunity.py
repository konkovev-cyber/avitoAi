"""Opportunity Engine — находит рыночные возможности из Market Graph."""

from __future__ import annotations

import hashlib
from ..graph.models import MarketGraph, GraphEntity
from ..models.opportunity import Opportunity


def _hash(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:8]


class OpportunityEngine:
    """Находит проверяемые рыночные возможности из Market Graph."""

    def scan(self, graph: MarketGraph) -> list[Opportunity]:
        """Просканировать граф, вернуть список найденных возможностей."""
        opportunities = []
        entities = list(graph.entities.values())

        opps = [
            *self._signal_weak_digital_presence(entities),
            *self._signal_marketplace_dependency(entities),
            *self._signal_multi_source_conflict(entities),
            *self._signal_competitor_gap(entities, graph),
            *self._signal_single_source_risk(entities),
            *self._signal_no_phone(entities),
            *self._signal_no_website(entities),
            *self._signal_expansion_opportunity(entities),
        ]

        for opp in opps:
            opportunities.append(opp)

        return opportunities

    # ── Signal 001: Weak Digital Presence ───────────────────────────────

    def _signal_weak_digital_presence(self, entities: list[GraphEntity]) -> list[Opportunity]:
        """Продавец есть на площадках, но нет сайта."""
        results = []

        for e in entities:
            has_website = bool(e.website)
            has_listings = len(e.source_listing_ids) >= 1

            if has_listings and not has_website and e.status in ("verified", "candidate"):
                results.append(Opportunity(
                    id=self._make_id("weak_presence", e.id),
                    type="weak_digital_presence",
                    severity="medium",
                    confidence=0.70,
                    entity_ids=[e.id],
                    entity_names=[e.name],
                    evidence=[
                        f"Активность на {len(e.source_listing_ids)} площадках",
                        "Сайт не обнаружен",
                    ],
                    message=f"У {e.name} нет сайта при наличии активности",
                    recommendation="Проверить потребность в цифровом канале",
                    status="candidate",
                ))

        return results

    # ── Signal 002: Marketplace Dependency ──────────────────────────────

    def _signal_marketplace_dependency(self, entities: list[GraphEntity]) -> list[Opportunity]:
        """Продавец зависит от одной площадки."""
        results = []

        for e in entities:
            sources = set(s.split("_")[0] for s in e.source_listing_ids if "_" in s)
            if len(sources) == 1 and e.status in ("verified", "candidate"):
                platform = list(sources)[0]
                results.append(Opportunity(
                    id=self._make_id("marketplace_dep", e.id),
                    type="marketplace_dependency",
                    severity="high" if platform in ("ozon", "wb", "ymk") else "medium",
                    confidence=0.65,
                    entity_ids=[e.id],
                    entity_names=[e.name],
                    evidence=[
                        f"Присутствие только на {platform}",
                        "Другие площадки не обнаружены",
                    ],
                    message=f"{e.name} зависит от {platform}",
                    recommendation=f"Расширить присутствие за пределы {platform}",
                    status="candidate",
                ))

        return results

    # ── Signal 003: Multi-source Conflict ───────────────────────────────

    def _signal_multi_source_conflict(self, entities: list[GraphEntity]) -> list[Opportunity]:
        """Одна сущность имеет противоречивые данные из разных источников."""
        results = []

        for e in entities:
            if len(e.source_listing_ids) >= 2:
                if e.phone:
                    # Успешное объединение — не конфликт, а триангуляция
                    continue
                # Нет телефона, но есть в нескольких источниках — данные неполные
                results.append(Opportunity(
                    id=self._make_id("conflict", e.id),
                    type="multi_source_conflict",
                    severity="low",
                    confidence=0.45,
                    entity_ids=[e.id],
                    entity_names=[e.name],
                    evidence=[
                        f"Найден в {len(e.source_listing_ids)} источниках",
                        "Телефон не обнаружен ни в одном",
                    ],
                    message=f"У {e.name} нет телефона при наличии в нескольких источниках",
                    recommendation="Проверить полноту данных источника",
                    status="hypothesis",
                ))

        return results

    # ── Signal 004: Competitor Gap ──────────────────────────────────────

    def _signal_competitor_gap(self, entities: list[GraphEntity], graph: MarketGraph) -> list[Opportunity]:
        """В категории доминирует мало участников."""
        if len(entities) < 3:
            return []

        # Оцениваем концентрацию: если топ-3 покрывают > 60% sources
        by_sources = sorted(entities, key=lambda e: len(e.source_listing_ids), reverse=True)
        top3 = by_sources[:3]
        total_sources = sum(len(e.source_listing_ids) for e in entities)

        if total_sources == 0:
            return []

        top3_share = sum(len(e.source_listing_ids) for e in top3) / total_sources

        if top3_share > 0.60:
            return [Opportunity(
                id=self._make_id("competitor_gap", "market"),
                type="competitor_gap",
                severity="medium",
                confidence=0.55,
                entity_ids=[e.id for e in top3],
                entity_names=[e.name for e in top3],
                evidence=[
                    f"Топ-3 покрывают {top3_share:.0%} присутствия",
                    f"Всего участников: {len(entities)}",
                ],
                message=f"Рынок концентрирован: топ-3 занимают {top3_share:.0%}",
                recommendation="Оценить возможность входа в нишу",
                status="candidate",
            )]

        return []

    # ── Signal 005: Single Source Risk ──────────────────────────────────

    def _signal_single_source_risk(self, entities: list[GraphEntity]) -> list[Opportunity]:
        """Продавец есть только в одном источнике."""
        results = []

        for e in entities:
            sources = set(s.split("_")[0] for s in e.source_listing_ids if "_" in s)
            if len(sources) == 0:
                continue
            if len(sources) == 1 and e.status in ("verified", "candidate"):
                platform = list(sources)[0]
                results.append(Opportunity(
                    id=self._make_id("single_source", e.id),
                    type="single_source_risk",
                    severity="medium",
                    confidence=0.60,
                    entity_ids=[e.id],
                    entity_names=[e.name],
                    evidence=[
                        f"Весь бизнес на {platform}",
                        "Диверсификация отсутствует",
                    ],
                    message=f"{e.name} представлен только на {platform}",
                    recommendation=f"Проанализировать возможность выхода на другие площадки",
                    status="candidate",
                ))

        return results

    # ── Signal 006: No Phone ────────────────────────────────────────────

    def _signal_no_phone(self, entities: list[GraphEntity]) -> list[Opportunity]:
        """Верифицированный продавец без телефона."""
        results = []

        for e in entities:
            if not e.phone and e.status == "verified":
                results.append(Opportunity(
                    id=self._make_id("no_phone", e.id),
                    type="no_phone",
                    severity="high",
                    confidence=0.75,
                    entity_ids=[e.id],
                    entity_names=[e.name],
                    evidence=[
                        "Продавец верифицирован",
                        "Телефон не обнаружен",
                    ],
                    message=f"У {e.name} нет телефона",
                    recommendation="CRM/телефония для приёма заказов",
                    status="candidate",
                ))

        return results

    # ── Signal 007: No Website ──────────────────────────────────────────

    def _signal_no_website(self, entities: list[GraphEntity]) -> list[Opportunity]:
        """Верифицированный продавец без сайта."""
        results = []

        for e in entities:
            if not e.website and e.status == "verified":
                results.append(Opportunity(
                    id=self._make_id("no_website", e.id),
                    type="no_website",
                    severity="medium",
                    confidence=0.70,
                    entity_ids=[e.id],
                    entity_names=[e.name],
                    evidence=[
                        "Продавец верифицирован",
                        "Сайт не обнаружен",
                    ],
                    message=f"У {e.name} нет сайта",
                    recommendation="Создание / продвижение сайта",
                    status="candidate",
                ))

        return results

    # ── Signal 008: Expansion Opportunity ───────────────────────────────

    def _signal_expansion_opportunity(self, entities: list[GraphEntity]) -> list[Opportunity]:
        """Продавец с сильным присутствием, но на одной площадке."""
        results = []

        for e in entities:
            sources = set(s.split("_")[0] for s in e.source_listing_ids if "_" in s)
            total_listings = len(e.source_listing_ids)

            if len(sources) == 1 and total_listings >= 2 and e.status in ("verified", "candidate"):
                results.append(Opportunity(
                    id=self._make_id("expansion", e.id),
                    type="expansion_opportunity",
                    severity="low",
                    confidence=0.55,
                    entity_ids=[e.id],
                    entity_names=[e.name],
                    evidence=[
                        f"Активен: {total_listings} предложений",
                        f"Площадка: {list(sources)[0]}",
                        "Другие площадки не задействованы",
                    ],
                    message=f"{e.name} может расшириться на другие площадки",
                    recommendation="Мультиканальная стратегия",
                    status="candidate",
                ))

        return results

    @staticmethod
    def _make_id(opp_type: str, entity_id: str) -> str:
        raw = f"{opp_type}_{entity_id}"
        return f"opp_{_hash(raw)}"

    @staticmethod
    def report(opportunities: list[Opportunity]) -> str:
        """Сформировать текстовый отчёт по возможностям."""
        if not opportunities:
            return "  Возможностей не найдено."

        lines = []
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "🔵"}
        actionable = [o for o in opportunities if o.is_actionable]

        if actionable:
            lines.append(f"  🔥 Приоритетные ({len(actionable)}):")
            for o in actionable:
                emoji = severity_emoji.get(o.severity, "⚪")
                lines.append(f"    {emoji} {o.message}")
                for ev in o.evidence:
                    lines.append(f"       → {ev}")
                lines.append(f"       💡 {o.recommendation}")
                lines.append("")

        others = [o for o in opportunities if not o.is_actionable]
        if others:
            lines.append(f"  📋 Остальные ({len(others)}):")
            for o in others:
                emoji = severity_emoji.get(o.severity, "⚪")
                lines.append(f"    {emoji} [{o.severity}] {o.message}")

        return "\n".join(lines)
