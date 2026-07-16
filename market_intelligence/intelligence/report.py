"""Report Engine — Market Intelligence Report из Market Graph."""

from __future__ import annotations

from ..graph.models import MarketGraph
from .scorer import SellerScorer, MarketScorer


class MarketReport:
    """Формирует читаемый Market Intelligence Report из Market Graph."""

    def __init__(self):
        self.seller_scorer = SellerScorer()
        self.market_scorer = MarketScorer()

    def generate(self, graph: MarketGraph) -> str:
        """Сформировать полный отчёт."""
        lines = []

        # ── Header ─────────────────────────────────────────────────────
        lines.append("📊 Market Intelligence Report")
        lines.append("=" * 50)
        lines.append("")

        # ── Market Summary ─────────────────────────────────────────────
        lines.append("📈 Обзор рынка")
        lines.append("-" * 30)
        summary = self.market_scorer.market_summary(graph)
        lines.append(f"  Участников:     {summary['total_entities']}")
        lines.append(f"  Связей:         {summary['total_relationships']}")
        lines.append(f"  Верифицировано: {summary['verified']}")
        lines.append(f"  Источников:     {summary['sources_used']}")
        lines.append("")

        # Распределение по типам
        lines.append("  По типам:")
        for etype, count in sorted(summary["by_type"].items()):
            lines.append(f"    {etype}: {count}")
        lines.append("")

        # Контакты
        lines.append("  Контакты:")
        lines.append(f"    С телефоном:    {summary['with_phone']}")
        lines.append(f"    С сайтом:       {summary['with_website']}")
        lines.append(f"    С ИНН:          {summary['with_inn']}")
        lines.append("")

        # ── Top Players ────────────────────────────────────────────────
        lines.append("🏆 Топ участников рынка")
        lines.append("-" * 30)

        all_scores = [
            self.seller_scorer.visibility_score(e, graph)
            for e in graph.entities.values()
        ]
        top5 = self.seller_scorer.top_players(all_scores, 5)

        if top5:
            for i, s in enumerate(top5, 1):
                lines.append(f"  {i}. {s['name']}")
                lines.append(f"     Score: {s['total_score']}/100 | "
                             f"Тип: {s['type']} | Статус: {s['status']}")
                lines.append(f"     Источников: {s['source_count']} | "
                             f"Доказательств: {s['evidence_count']}")
                lines.append(f"     Детали: {self._format_breakdown(s['breakdown'])}")
                lines.append("")
        else:
            lines.append("  Нет данных для ранжирования.\n")

        # ── Visibility Distribution ────────────────────────────────────
        lines.append("📊 Распределение Visibility Score")
        lines.append("-" * 30)

        if all_scores:
            buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
            for s in all_scores:
                score = s["total_score"]
                if score <= 20:
                    buckets["0-20"] += 1
                elif score <= 40:
                    buckets["21-40"] += 1
                elif score <= 60:
                    buckets["41-60"] += 1
                elif score <= 80:
                    buckets["61-80"] += 1
                else:
                    buckets["81-100"] += 1

            for bucket, count in buckets.items():
                bar = "█" * (count * 2) if count else "—"
                lines.append(f"  {bucket}: {bar} ({count})")
            lines.append("")

        # ── Opportunity Signals ────────────────────────────────────────
        lines.append("🎯 Найденные возможности")
        lines.append("-" * 30)

        signals = self.market_scorer.opportunity_signals(graph)
        if signals:
            severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for s in signals:
                emoji = severity_emoji.get(s["severity"], "⚪")
                lines.append(f"  {emoji} [{s['severity'].upper()}] {s['message']}")
                lines.append(f"     → {s['opportunity']}")
                if s.get("examples"):
                    lines.append(f"     Примеры: {', '.join(s['examples'])}")
                lines.append("")
        else:
            lines.append("  Возможностей не найдено.\n")

        # ── Footer ────────────────────────────────────────────────────
        lines.append("=" * 50)
        lines.append("Evidence First · Market Intelligence OS")

        return "\n".join(lines)

    @staticmethod
    def _format_breakdown(breakdown: dict) -> str:
        """Форматировать детализацию Score."""
        parts = [f"{k}={v}" for k, v in sorted(breakdown.items())]
        return ", ".join(parts)
