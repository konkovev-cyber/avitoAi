"""Recommendation — формирование рекомендаций из Lead."""

from __future__ import annotations

from typing import Optional
from ...models.lead import Lead
from ...models.opportunity import Opportunity


ACTION_TEMPLATES = {
    "digital_expansion": {
        "label": "Цифровая экспансия",
        "description": "Продавец есть на рынке, но не имеет собственного цифрового канала",
        "next_steps": [
            "Проверить возможность создания сайта",
            "Проанализировать SEO-потенциал",
            "Оценить бюджет на разработку",
        ],
    },
    "channel_diversification": {
        "label": "Диверсификация каналов",
        "description": "Продавец использует только одну площадку",
        "next_steps": [
            "Исследовать дополнительные маркетплейсы",
            "Проверить условия альтернативных площадок",
            "Оценить стоимость выхода на новые каналы",
        ],
    },
    "growth_opportunity": {
        "label": "Потенциал роста",
        "description": "Высокая активность при слабой представленности",
        "next_steps": [
            "Провести анализ конкурентной среды",
            "Разработать стратегию расширения",
            "Оценить потенциал категории",
        ],
    },
    "local_presence_gap": {
        "label": "Географическое расширение",
        "description": "Продавец активен локально, но не представлен в других регионах",
        "next_steps": [
            "Проанализировать регионы с отсутствием продавца",
            "Проверить логистические возможности",
            "Оценить спрос в целевых регионах",
        ],
    },
    "marketplace_optimization": {
        "label": "Оптимизация маркетплейсов",
        "description": "Продавец на маркетплейсе, но карточки не оптимизированы",
        "next_steps": [
            "Проанализировать качество карточек товаров",
            "Проверить ключевые слова и описание",
            "Оценить рекламный потенциал",
        ],
    },
}


def get_recommendation(lead: Lead) -> dict:
    """Получить структурированную рекомендацию для Lead."""
    template = ACTION_TEMPLATES.get(lead.type, {
        "label": lead.type.replace("_", " ").title(),
        "description": "",
        "next_steps": [],
    })

    return {
        "lead_id": lead.id,
        "target": lead.entity_name,
        "type": lead.type,
        "confidence": lead.score / 100.0,
        "label": template["label"],
        "description": template["description"],
        "priority": lead.priority,
        "recommended_action": lead.recommended_action,
        "evidence": lead.evidence,
        "next_steps": template["next_steps"],
        "automated": False,
    }


def generate_commercial_report(leads: list[Lead]) -> str:
    """Сформировать коммерческий отчёт."""
    lines = [
        "📊 COMMERCIAL INTELLIGENCE REPORT",
        "=" * 56,
        "",
        f"Найдено лидов: {len(leads)}",
        f"Actionable: {sum(1 for l in leads if l.is_actionable)}",
        "",
    ]

    actionable = [l for l in leads if l.is_actionable]
    if actionable:
        lines.append("🔥 ПРИОРИТЕТНЫЕ ЛИДЫ")
        lines.append("-" * 56)
        for lead in actionable[:5]:
            entity_name = lead.entity_name or "?"
            lines.append("")
            lines.append(f"  [{lead.score}/100] {lead.type}")
            lines.append(f"  Компания: {entity_name}")
            lines.append(f"  Приоритет: {lead.priority}")
            lines.append(f"  Действие: {lead.recommended_action}")
            lines.append(f"  Evidence:")
            for ev in lead.evidence[:3]:
                lines.append(f"    → {ev}")
            lines.append("")

    others = [l for l in leads if not l.is_actionable]
    if others:
        lines.append(f"📋 Остальные ({len(others)}):")
        for lead in others:
            lines.append(f"  [{lead.score}/100] {lead.type}: {lead.entity_name}")

    lines.append("")
    lines.append("=" * 56)
    lines.append("Market Intelligence OS · Commercial Intelligence")

    return "\n".join(lines)
