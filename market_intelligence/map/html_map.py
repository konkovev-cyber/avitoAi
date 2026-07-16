"""HTML Map — генерация HTML-страницы карты рынка."""

from __future__ import annotations

from ..graph.models import MarketGraph, GraphEntity
from ..models.opportunity import Opportunity
from ..intelligence.scorer import SellerScorer, MarketScorer
from ..intelligence.opportunity import OpportunityEngine
from .entity_graph import render_entity_graph, _source_label


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Intelligence Map</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       background: #0b0f19; color: #e2e8f0; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
h1 {{ font-size: 1.8rem; color: #38bdf8; margin-bottom: 24px; }}
h2 {{ font-size: 1.2rem; color: #94a3b8; margin-bottom: 16px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 24px; }}
.card {{ background: #1e293b; border-radius: 10px; padding: 16px; border: 1px solid #334155; }}
.card h3 {{ font-size: 0.7rem; text-transform: uppercase; color: #64748b; }}
.card .value {{ font-size: 1.8rem; font-weight: 700; color: #38bdf8; }}
.card .sub {{ font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }}
.entity-card {{ background: #1e293b; border-radius: 10px; padding: 16px; margin-bottom: 12px; border: 1px solid #334155; }}
.entity-name {{ font-size: 1.1rem; font-weight: 600; color: #f1f5f9; }}
.entity-type {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: #334155; margin-left: 8px; }}
.entity-status {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
.status-verified {{ background: #22c55e; }}
.status-candidate {{ background: #eab308; }}
.status-hypothesis {{ background: #64748b; }}
.contacts {{ font-size: 0.85rem; color: #94a3b8; margin: 8px 0; }}
.sources {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }}
.source-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; background: #334155; }}
.opportunity {{ padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; border: 1px solid; }}
.opp-critical {{ background: #2d1b1b; border-color: #ef4444; }}
.opp-high {{ background: #2d2115; border-color: #f97316; }}
.opp-medium {{ background: #1e293b; border-color: #eab308; }}
.opp-low {{ background: #1a2e1a; border-color: #22c55e; }}
.opp-evidence {{ font-size: 0.8rem; color: #94a3b8; margin: 4px 0 0 16px; }}
.evidence-chain {{ background: #0f172a; border-radius: 6px; padding: 10px; margin-top: 8px; font-size: 0.8rem; color: #94a3b8; }}
.human-review {{ margin-top: 8px; display: flex; gap: 8px; }}
.human-btn {{ padding: 4px 12px; border-radius: 4px; border: 1px solid #334155; background: #1e293b; color: #e2e8f0; cursor: pointer; font-size: 0.8rem; }}
.human-btn:hover {{ background: #334155; }}
.footer {{ margin-top: 40px; font-size: 0.75rem; color: #475569; text-align: center; }}
pre {{ font-family: 'Courier New', monospace; font-size: 0.8rem; color: #94a3b8; line-height: 1.5; }}
a {{ color: #38bdf8; text-decoration: none; }}
</style>
</head>
<body>
<div class="container">
<h1>🗺 Market Intelligence Map</h1>
{content}
<div class="footer">
Market Intelligence OS &middot; Evidence First &middot; Phase 3
</div>
</div>
</body>
</html>"""


class HTMLMapRenderer:
    """Генерация HTML-карты рынка."""

    def __init__(self, graph: MarketGraph, opportunities: list[Opportunity] | None = None):
        self.graph = graph
        self.opportunities = opportunities or []
        self.seller_scorer = SellerScorer()
        self.market_scorer = MarketScorer()

    def render(self) -> str:
        """Сформировать полную HTML-страницу."""
        sections = []

        # 1. Market Overview
        sections.append(self._render_overview())
        sections.append(self._render_opportunities())
        sections.append(self._render_entities())

        return HTML_TEMPLATE.format(content="\n".join(sections))

    def _render_overview(self) -> str:
        summary = self.market_scorer.market_summary(self.graph)
        html = ['<h2>📊 Обзор рынка</h2>', '<div class="grid">']

        cards = [
            ("Всего участников", str(summary["total_entities"]), "verified + hypothesis"),
            ("Верифицировано", str(summary["verified"]), f'{summary["verified"]}/{summary["total_entities"]}' if summary["total_entities"] else "0"),
            ("Источников", str(summary["sources_used"]), "подключено"),
            ("Связей", str(summary["total_relationships"]), "relationships"),
            ("С телефоном", str(summary["with_phone"]), f'{summary["with_phone"]}/{summary["total_entities"]}' if summary["total_entities"] else "0"),
            ("С сайтом", str(summary["with_website"]), f'{summary["with_website"]}/{summary["total_entities"]}' if summary["total_entities"] else "0"),
        ]

        for label, value, sub in cards:
            html.append(f'<div class="card"><h3>{label}</h3><div class="value">{value}</div><div class="sub">{sub}</div></div>')

        # По типам
        if summary.get("by_type"):
            html.append('<div class="card"><h3>По типам</h3>')
            for etype, count in sorted(summary["by_type"].items()):
                html.append(f'<div class="sub">{etype}: {count}</div>')
            html.append("</div>")

        html.append("</div>")
        return "\n".join(html)

    def _render_opportunities(self) -> str:
        if not self.opportunities:
            return ""

        html = ['<h2>🎯 Возможности</h2>']

        severity_class = {"critical": "opp-critical", "high": "opp-high",
                          "medium": "opp-medium", "low": "opp-low"}
        severity_label = {"critical": "🔴 Критично", "high": "🟠 Высокий",
                          "medium": "🟡 Средний", "low": "🟢 Низкий"}

        for opp in self.opportunities:
            cls = severity_class.get(opp.severity, "opp-medium")
            label = severity_label.get(opp.severity, "⚪")
            html.append(f'<div class="opportunity {cls}">')
            html.append(f'  <div style="font-weight: 600;">{label}: {opp.message}</div>')
            html.append(f'  <div style="font-size:0.85rem; color: #94a3b8; margin-top: 4px;">'
                        f'Уверенность: {opp.confidence:.0%} | Статус: {opp.status}</div>')
            if opp.evidence:
                html.append(f'  <div class="opp-evidence">')
                for ev in opp.evidence:
                    html.append(f'    → {ev}')
                html.append('  </div>')
            if opp.recommendation:
                html.append(f'  <div style="font-size:0.85rem; color: #60a5fa; margin-top: 4px;">💡 {opp.recommendation}</div>')

            # Human Review
            html.append(f'  <div class="human-review">')
            if opp.status == "candidate":
                html.append(f'    <span style="font-size:0.75rem; color:#64748b;">Статус: кандидат — требуется проверка</span>')
            elif opp.status == "validated":
                html.append(f'    <span style="font-size:0.75rem; color:#22c55e;">✅ Подтверждено человеком</span>')
            elif opp.status == "dismissed":
                html.append(f'    <span style="font-size:0.75rem; color:#ef4444;">❌ Отклонено</span>')
            html.append('  </div>')
            html.append('</div>')

        return "\n".join(html)

    def _render_entities(self) -> str:
        if not self.graph.entities:
            return '<div class="entity-card">Нет данных</div>'

        html = ['<h2>🏢 Участники рынка</h2>']

        for entity in self.graph.entities.values():
            txt_lines = render_entity_graph(entity, self.graph)
            html.append('<div class="entity-card">')
            html.append('<pre>')
            html.append("\n".join(txt_lines))
            html.append('</pre>')

            # Evidence chain
            if entity.evidence_ids:
                html.append('<details><summary style="cursor:pointer; font-size:0.85rem; color:#64748b;">🔍 Evidence Chain</summary>')
                html.append('<div class="evidence-chain">')
                for eid in entity.evidence_ids[:5]:
                    html.append(f'  📄 {eid}')
                if len(entity.evidence_ids) > 5:
                    html.append(f'  … и ещё {len(entity.evidence_ids) - 5}')
                html.append('</div></details>')

            html.append('</div>')

        return "\n".join(html)
