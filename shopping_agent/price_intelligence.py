"""Price Intelligence — анализ цен на рынке."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PriceInsight:
    """Результат анализа цены для товара."""
    market_avg: float = 0.0
    market_min: float = 0.0
    market_max: float = 0.0
    sample_size: int = 0
    median: float = 0.0


@dataclass
class DealScore:
    """Оценка выгодности предложения."""
    price: float
    savings: float = 0.0          # экономия от средней
    savings_pct: float = 0.0      # процент экономии
    price_rank: int = 0           # место по цене (1 = самая низкая)
    market_position: str = ""     # below_average | average | above_average | suspicious
    explanation: str = ""


class PriceAnalyzer:
    """Анализ цен и вычисление выгоды."""

    def analyze(self, prices: list[float]) -> PriceInsight:
        """Вычислить рыночную статистику."""
        if not prices:
            return PriceInsight()

        sorted_prices = sorted(prices)
        n = len(sorted_prices)

        return PriceInsight(
            market_avg=sum(prices) / n,
            market_min=sorted_prices[0],
            market_max=sorted_prices[-1],
            sample_size=n,
            median=sorted_prices[n // 2] if n % 2 else (sorted_prices[n//2-1] + sorted_prices[n//2]) / 2,
        )

    def score_deal(self, price: float, insight: PriceInsight, all_prices: list[float]) -> DealScore:
        """Оценить выгодность конкретной цены."""
        if insight.market_avg == 0:
            return DealScore(price=price, market_position="unknown")

        savings = insight.market_avg - price
        savings_pct = (savings / insight.market_avg * 100) if insight.market_avg else 0

        # Price rank
        sorted_prices = sorted(set(all_prices))
        rank = 1
        for p in sorted_prices:
            if p <= price:
                rank = sorted_prices.index(p) + 1

        # Market position
        if savings_pct > 15:
            position = "below_average"
            explanation = f"Экономия {savings:,.0f}₽ ({savings_pct:.0f}% ниже средней)"
        elif savings_pct > 5:
            position = "below_average"
            explanation = f"Ниже средней на {savings:,.0f}₽"
        elif savings_pct > -5:
            position = "average"
            explanation = f"На уровне рынка"
        elif savings_pct > -15:
            position = "above_average"
            explanation = f"Выше средней на {-savings:,.0f}₽"
        else:
            position = "suspicious"
            explanation = f"Подозрительно дешёвое ({savings_pct:.0f}% ниже рынка — возможен обман)"

        # Suspicious low price
        if savings_pct > 40:
            position = "suspicious"
            explanation = f"⚠️ Подозрительно дешёвое — проверьте продавца"

        return DealScore(
            price=price,
            savings=max(savings, 0),
            savings_pct=savings_pct,
            price_rank=rank,
            market_position=position,
            explanation=explanation,
        )
