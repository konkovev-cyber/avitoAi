"""Entity Graph — ASCII-рендеринг графа сущностей."""

from __future__ import annotations

from typing import Optional

from ..graph.models import MarketGraph, GraphEntity


def render_entity_graph(
    entity: GraphEntity,
    graph: MarketGraph,
    max_depth: int = 2,
) -> list[str]:
    """Построить ASCII-граф вокруг одной сущности."""
    lines = []
    name = entity.name or entity.id

    # Заголовок
    status_icon = {"verified": "✅", "candidate": "🟡", "hypothesis": "⚪"}.get(entity.status, "❓")
    lines.append(f"  {status_icon} {name}")
    lines.append(f"     Тип: {entity.type} | Статус: {entity.status}")
    lines.append(f"     Confidence: {entity.confidence:.2f}")

    # Контакты
    contacts = []
    if entity.phone:
        contacts.append(f"📞 {entity.phone[:12]}…")
    if entity.email:
        contacts.append(f"✉️ {entity.email}")
    if entity.website:
        contacts.append(f"🌐 {entity.website}")
    if entity.inn:
        contacts.append(f"📋 ИНН:{entity.inn}")
    if contacts:
        lines.append("     " + " | ".join(contacts))

    # Источники
    if entity.source_listing_ids:
        sources = {}
        for sid in entity.source_listing_ids:
            prefix = sid.split("_")[0] if "_" in sid else sid
            src_label = _source_label(prefix)
            sources[src_label] = sources.get(src_label, 0) + 1
        lines.append("")
        lines.append("     📦 Источники:")
        for src, count in sorted(sources.items()):
            lines.append(f"       {_source_emoji(src)} {src}: {count}")
    else:
        lines.append("     (нет данных об источниках)")

    # Evidence
    if entity.evidence_ids:
        lines.append("")
        lines.append(f"     🔗 Evidence: {len(entity.evidence_ids)} записей")

    # Связи
    rels = graph.get_relationships(entity.id)
    if rels:
        lines.append("")
        for rel in rels:
            other_id = rel.target_id if rel.source_id == entity.id else rel.source_id
            other = graph.get_entity(other_id)
            other_name = other.name if other else other_id[:16]
            rel_icon = {"same_as": "🔗", "sells": "🛒", "unknown": "🔹"}.get(rel.type, "🔸")
            lines.append(f"     {rel_icon} {rel.type}: {other_name}")

    return lines


def render_market_map(graph: MarketGraph, entity_ids: Optional[list[str]] = None) -> str:
    """
    Рендеринг полной карты рынка (текстовой).

    Если entity_ids указан — только указанные сущности.
    """
    lines = []
    lines.append("=" * 56)
    lines.append("  🗺  MARKET MAP — Market Intelligence OS")
    lines.append("=" * 56)

    entities_to_show = list(graph.entities.values())
    if entity_ids:
        entities_to_show = [e for e in entities_to_show if e.id in entity_ids]

    if not entities_to_show:
        lines.append("  (пусто)")

    for entity in entities_to_show:
        lines.append("")
        lines.extend(render_entity_graph(entity, graph))
        lines.append("")

    # Сводка
    lines.append("-" * 56)
    stats = graph.get_stats()
    lines.append(
        f"  Участников: {stats['total_entities']} | "
        f"Связей: {stats['total_relationships']} | "
        f"Верифицировано: {stats['verified_entities']}"
    )
    lines.append("=" * 56)

    return "\n".join(lines)


def _source_label(prefix: str) -> str:
    labels = {
        "ym": "Yandex Maps", "av": "Avito", "site": "Сайт",
        "ymk": "Yandex Market", "oz": "Ozon", "wb": "Wildberries",
        "youla": "Юла",
    }
    return labels.get(prefix, prefix)


def _source_emoji(src: str) -> str:
    emojis = {
        "Yandex Maps": "🗺", "Avito": "📰", "Сайт": "🌐",
        "Yandex Market": "🛒", "Ozon": "📦", "Wildberries": "🧺",
    }
    return emojis.get(src, "📌")
