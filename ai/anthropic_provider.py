"""Anthropic Claude provider for Market Agent AI analysis."""

from __future__ import annotations

import json
import logging
from typing import Optional

from ai.base import AIProvider, AIAnalysis, IntentParsed, MarketRadarItem

log = logging.getLogger("market_agent.ai.anthropic")

_ANALYZE_SYSTEM = (
    "Ты — AI аналитик рынка подержанных товаров. "
    "Отвечай строго в JSON. Используй русский язык для текстовых полей."
)

_ANALYZE_TMPL = """Объявление:
Название: {title}
Цена: {price} ₽ | Рынок: {market_price} ₽ | Отклонение: {price_delta_pct:+.1f}%
Описание: {description}
Продавец: {seller_name} (рейтинг: {seller_rating}) | Фото: {images_count} | Похожих: {similar_count}

JSON ответ:
{{
  "explanation": "1-2 предложения объяснения",
  "why_good": ["причина"],
  "risks": ["риск"],
  "ai_score": 80,
  "recommendation": "maybe",
  "confidence": 0.8
}}"""


class AnthropicProvider(AIProvider):
    """Anthropic Claude Haiku / Sonnet provider."""

    def __init__(self, api_key: str, model: str = "claude-haiku-4-5"):
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def name(self) -> str:
        return f"Claude ({self._model})"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            except ImportError:
                log.error("anthropic package not installed. Run: pip install anthropic")
                return None
        return self._client

    async def _message(self, system: str, user: str) -> Optional[str]:
        client = self._get_client()
        if not client:
            return None
        try:
            resp = await client.messages.create(
                model=self._model,
                max_tokens=800,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return resp.content[0].text
        except Exception as e:
            log.warning("Anthropic API error: %s", e)
            return None

    def _parse_json_from_text(self, text: str) -> Optional[dict]:
        """Extract JSON from Claude's response (may include text before/after)."""
        try:
            # Try direct parse first
            return json.loads(text)
        except Exception:
            pass
        # Find JSON block
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except Exception:
                pass
        return None

    async def analyze_listing(
        self,
        title: str,
        price: float,
        market_price: float,
        description: str,
        seller_name: str,
        seller_rating: Optional[float],
        images_count: int,
        similar_count: int,
        price_delta_pct: float,
    ) -> AIAnalysis:
        prompt = _ANALYZE_TMPL.format(
            title=title[:200],
            price=price,
            market_price=market_price,
            price_delta_pct=price_delta_pct,
            description=(description or "нет описания")[:500],
            seller_name=seller_name or "неизвестен",
            seller_rating=seller_rating or "нет",
            images_count=images_count,
            similar_count=similar_count,
        )
        raw = await self._message(_ANALYZE_SYSTEM, prompt)
        if not raw:
            return AIAnalysis(provider=self.name)
        data = self._parse_json_from_text(raw)
        if not data:
            return AIAnalysis(provider=self.name)
        try:
            return AIAnalysis(
                explanation=data.get("explanation", ""),
                why_good=data.get("why_good", []),
                risks=data.get("risks", []),
                ai_score=float(data.get("ai_score", 0)),
                recommendation=data.get("recommendation", "maybe"),
                confidence=float(data.get("confidence", 0)),
                provider=self.name,
            )
        except Exception:
            return AIAnalysis(provider=self.name)

    async def explain_deal(
        self,
        title: str,
        price: float,
        market_price: float,
        similar_count: int,
        price_delta_pct: float,
        percentile_position: float,
    ) -> str:
        cheaper_pct = int(percentile_position * 100)
        savings = market_price - price
        prompt = (
            f"Товар: {title}. Цена: {price:,.0f} ₽ (рынок: {market_price:,.0f} ₽). "
            f"Дешевле {cheaper_pct}% из {similar_count} объявлений. "
            f"Экономия: {savings:,.0f} ₽.\n"
            "Объяснение в 2-3 предложения от AI агента, начни с 'Я сравнил...'. "
            "JSON: {\"text\": \"объяснение\"}"
        )
        raw = await self._message(
            "Ты AI помощник по покупкам. Отвечай только JSON на русском языке.",
            prompt,
        )
        if not raw:
            return (
                f"Я сравнил {similar_count} похожих объявлений. "
                f"Средняя цена {market_price:,.0f} ₽. "
                f"Это предложение дешевле {cheaper_pct}% рынка."
            )
        data = self._parse_json_from_text(raw)
        return data.get("text", "") if data else ""

    async def parse_intent(self, text: str) -> IntentParsed:
        prompt = (
            f"Поисковый запрос: {text[:500]}\n"
            "Извлеки: query, keywords[], category, max_price, location, condition, purpose.\n"
            "JSON: {\"query\": \"\", \"keywords\": [], \"category\": \"\", "
            "\"max_price\": null, \"location\": null, \"condition\": \"any\", "
            "\"purpose\": \"self\", \"confidence\": 0.95}"
        )
        raw = await self._message(
            "Ты парсер запросов маркетплейса. Отвечай только JSON.", prompt
        )
        if not raw:
            return IntentParsed(query=text, keywords=text.split())
        data = self._parse_json_from_text(raw)
        if not data:
            return IntentParsed(query=text, keywords=text.split())
        try:
            return IntentParsed(
                query=data.get("query", text),
                keywords=data.get("keywords", text.split()),
                category=data.get("category", ""),
                max_price=data.get("max_price"),
                location=data.get("location"),
                condition=data.get("condition", "any"),
                purpose=data.get("purpose", "self"),
                confidence=float(data.get("confidence", 0.9)),
            )
        except Exception:
            return IntentParsed(query=text, keywords=text.split())

    async def generate_market_radar(
        self, categories_data: list[dict]
    ) -> list[MarketRadarItem]:
        if not categories_data:
            return []
        data_str = json.dumps(categories_data, ensure_ascii=False)[:2000]
        prompt = (
            f"Данные по категориям товаров:\n{data_str}\n\n"
            "Для каждой категории: тренд цен, комментарий на русском. "
            "JSON массив: [{\"category\": \"...\", \"trend\": \"falling\", "
            "\"trend_pct\": -7.2, \"trend_emoji\": \"↓\", "
            "\"comment\": \"...\", \"hot_deals_count\": 0}]"
        )
        raw = await self._message(
            "Ты рыночный аналитик. Отвечай только JSON на русском.", prompt
        )
        if not raw:
            return []
        data = self._parse_json_from_text(raw)
        if not data:
            return []
        items = data if isinstance(data, list) else data.get("items", [])
        try:
            return [
                MarketRadarItem(
                    category=i.get("category", ""),
                    trend=i.get("trend", "stable"),
                    trend_pct=float(i.get("trend_pct", 0)),
                    trend_emoji=i.get("trend_emoji", "→"),
                    comment=i.get("comment", ""),
                    hot_deals_count=int(i.get("hot_deals_count", 0)),
                )
                for i in items
            ]
        except Exception as e:
            log.warning("Failed to parse Anthropic radar: %s", e)
            return []
