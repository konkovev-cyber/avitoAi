"""Alert formatter for Market Agent Telegram Bot."""

from __future__ import annotations


def format_alert(title: str, price: float, market_price: float,
                 deal_score: float, price_delta_pct: float,
                 risk_score: float, recommendation: str,
                 ai_explanation: str = "", ai_why_good: list = None,
                 ai_risks: list = None, url: str = "") -> str:
    """Format a deal alert card for Telegram (HTML)."""
    ai_why_good = ai_why_good or []
    ai_risks = ai_risks or []

    score_emoji = "🔥" if deal_score >= 70 else "✅" if deal_score >= 50 else "ℹ️"
    rec_emoji = "🟢" if recommendation == "buy" else "🟡" if recommendation == "maybe" else "⚪"

    savings = market_price - price
    savings_str = f"-{savings:,.0f} ₽ ({abs(price_delta_pct):.0f}%)" if savings > 0 else ""

    lines = [
        f"{score_emoji} <b>ВЫГОДНАЯ НАХОДКА</b>",
        "",
        f"<b>{title[:80]}</b>",
        "",
        f"💰 Цена: <b>{price:,.0f} ₽</b>",
        f"📊 Средняя цена: <b>{market_price:,.0f} ₽</b>",
    ]
    if savings_str:
        lines.append(f"📉 Экономия: <b>{savings_str}</b>")

    lines += [
        "",
        f"⭐ AI оценка: <b>{deal_score:.0f}/100</b>",
        f"{rec_emoji} Уверенность AI: <b>{risk_score:.0f}</b>",
    ]

    if ai_explanation:
        lines += ["", f"<i>{ai_explanation}</i>"]

    if ai_why_good:
        lines += ["", "Почему стоит посмотреть:"]
        lines += [f"✅ {r}" for r in ai_why_good[:3]]

    if ai_risks:
        lines += ["", "Риски:"]
        lines += [f"⚠️ {r}" for r in ai_risks[:2]]

    return "\n".join(lines)
