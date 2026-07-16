"""Deal Finder — объединение поиска, цен и доверия в финальную рекомендацию."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .query_parser import ProductQuery, parse_query
from .search_expander import expand_search, format_search_plan
from .price_intelligence import PriceAnalyzer, PriceInsight, DealScore
from .trust_scorer import SellerTrustScorer, TrustScore


@dataclass
class Deal:
    """Один вариант покупки."""
    title: str
    price: float
    source: str = ""
    seller_name: str = ""
    url: str = ""
    condition: str = "новый"

    # Calculated
    price_score: Optional[DealScore] = None
    trust_score: Optional[TrustScore] = None

    @property
    def total_score(self) -> float:
        """Комбинированный score (0-100)."""
        ts = self.trust_score.score if self.trust_score else 50
        ps = 100 - (self.price_score.price_rank * 5) if self.price_score else 50
        return round(ts * 0.6 + ps * 0.4, 1)

    @property
    def trust_level_emoji(self) -> str:
        if not self.trust_score:
            return "⚪"
        return {"high": "🟢", "medium": "🟡", "low": "🟠", "suspicious": "🔴"}.get(
            self.trust_score.level, "⚪")

    def format(self, rank: int) -> str:
        """Человекочитаемый формат."""
        lines = [
            f"{'🔥' if rank <= 3 else '  '} #{rank} {self.title}",
            f"     💰 {self.price:,.0f}₽".replace(",", " "),
        ]
        if self.price_score:
            if self.price_score.savings > 0:
                lines.append(f"     📉 Экономия: {self.price_score.savings:,.0f}₽ ({self.price_score.savings_pct:.0f}% от средней)".replace(",", " "))
            lines.append(f"     📊 {self.price_score.explanation}")
        lines.append(f"     {self.trust_level_emoji} Доверие: {self.trust_score.score if self.trust_score else '?'}/100")
        if self.trust_score:
            lines.append(f"        {self.trust_score.explanation}")
        if self.seller_name:
            lines.append(f"     👤 {self.seller_name}")
        if self.source:
            lines.append(f"     📦 {self.source}")
        return "\n".join(lines)


@dataclass
class SearchResult:
    """Результат поиска для пользователя."""
    query: ProductQuery
    search_variants: list[str] = field(default_factory=list)
    deals: list[Deal] = field(default_factory=list)
    insight: Optional[PriceInsight] = None
    message: str = ""

    def format_response(self, max_deals: int = 5) -> str:
        """Сформировать ответ пользователю."""
        lines = []

        if self.message:
            lines.append(self.message)
            return "\n".join(lines)

        lines.append(f"🔍 Нашёл по запросу: {self.query.summary()}")
        lines.append("")

        if not self.deals:
            lines.append("❌ Вариантов не найдено. Попробуйте изменить запрос.")
            return "\n".join(lines)

        # Market overview
        if self.insight and self.insight.sample_size > 0:
            lines.append(f"📊 Рынок: {self.insight.sample_size} предложений")
            lines.append(f"   Средняя: {self.insight.market_avg:,.0f}₽".replace(",", " "))
            lines.append(f"   Мин: {self.insight.market_min:,.0f}₽  Макс: {self.insight.market_max:,.0f}₽".replace(",", " "))
            lines.append("")

        # Top deals
        top = sorted(self.deals, key=lambda d: -d.total_score)[:max_deals]
        lines.append(f"🔥 Лучшие варианты ({len(top)} из {len(self.deals)}):")
        lines.append("")

        for i, deal in enumerate(top, 1):
            lines.append(deal.format(i))
            lines.append("")

        # Savings summary
        if self.insight and self.insight.market_avg > 0:
            best = top[0]
            if best.price_score and best.price_score.savings > 0:
                lines.append(f"💰 Лучший вариант дешевле средней на {best.price_score.savings:,.0f}₽".replace(",", " "))

        lines.append("")
        lines.append("Полезно? [✅ Да] [❌ Нет]")

        return "\n".join(lines)


class DealFinder:
    """Основной класс — поиск лучших вариантов покупки."""

    def __init__(self):
        self.price_analyzer = PriceAnalyzer()
        self.trust_scorer = SellerTrustScorer()

    def search(self, user_input: str, listings: list[dict]) -> SearchResult:
        """
        Полный цикл: запрос → расширение → анализ → рекомендация.

        listings format:
        [{"title": "...", "price": 74900, "source": "Avito",
          "seller_name": "...", "url": "...", "seller": {...}}]
        """
        # 1. Parse query
        query = parse_query(user_input)

        # 2. Expand search
        variants = expand_search(query)

        if not listings:
            return SearchResult(
                query=query,
                search_variants=variants,
                message="❌ Не удалось загрузить предложения. Попробуйте позже.",
            )

        # 3. Filter by budget
        filtered = listings
        if query.budget:
            filtered = [l for l in listings if l.get("price", 0) <= query.budget]

        if not filtered and query.budget:
            # Fallback: show cheapest even above budget
            filtered = sorted(listings, key=lambda x: x.get("price", 999999))[:5]

        # 4. Price analysis
        prices = [l["price"] for l in filtered if l.get("price", 0) > 0]
        insight = self.price_analyzer.analyze(prices)

        # 5. Score each deal
        deals = []
        for listing in filtered:
            price = listing.get("price", 0)
            if price <= 0:
                continue

            deal = Deal(
                title=listing.get("title", "Товар"),
                price=price,
                source=listing.get("source", ""),
                seller_name=listing.get("seller_name", ""),
                url=listing.get("url", ""),
                condition=listing.get("condition", "новый"),
            )

            # Price score
            deal.price_score = self.price_analyzer.score_deal(price, insight, prices)

            # Trust score
            seller_data = listing.get("seller", {})
            deal.trust_score = self.trust_scorer.score(seller_data)

            deals.append(deal)

        # 6. Sort by total score
        deals.sort(key=lambda d: -d.total_score)

        return SearchResult(
            query=query,
            search_variants=variants,
            deals=deals,
            insight=insight,
        )
