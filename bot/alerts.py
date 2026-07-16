"""Alert formatting for Telegram messages."""

from __future__ import annotations

from typing import Optional


def format_alert(row: dict) -> str:
    """Format a database alert row into a Telegram message."""
    title = row.get("title", "Без названия")
    price = row.get("price", 0)
    deal_score = row.get("deal_score", 0)
    recommendation = row.get("recommendation", "maybe")
    price_delta = row.get("price_delta_pct", 0)
    url = row.get("url", "")
    source = row.get("source", "?")

    score_emoji = "🔥" if deal_score >= 70 else "✅" if deal_score >= 50 else "ℹ️"
    delta_str = f"Ниже рынка: {abs(price_delta):.0f}%" if price_delta < 0 else f"Выше рынка: {price_delta:.0f}%"

    return (
        f"{score_emoji} <b>{title[:120]}</b>\n\n"
        f"💰 <b>{price:,.0f} ₽</b>\n"
        f"📊 {delta_str}\n"
        f"⭐ Оценка: <b>{deal_score:.0f}/100</b>\n"
        f"📱 {source.upper()}\n\n"
        f"🔗 {url}"
    )
