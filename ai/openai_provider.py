"""OpenAI GPT provider for Market Agent AI analysis."""

from __future__ import annotations

import json
import logging
from typing import Optional

from ai.base import AIProvider, AIAnalysis, IntentParsed, MarketRadarItem

log = logging.getLogger("market_agent.ai.openai")

_ANALYZE_SYSTEM = """Ты — AI аналитик рынка подержанных товаров (Авито, Юла).
Твоя задача — оценить объявление и дать чёткую рекомендацию покупателю.
Отвечай строго в JSON формате. Используй русский язык для текстовых полей."""

_ANALYZE_PROMPT = """Объявление:
Название: {title}
Цена: {price} ₽
Средняя цена рынка: {market_price} ₽
Отклонение от рынка: {price_delta_pct:+.1f}%
Описание: {description}
Продавец: {seller_name} (рейтинг: {seller_rating})
Фотографий: {images_count}
Похожих объявлений для сравнения: {similar_count}

Верни JSON:
{{
  "explanation": "краткое объяснение 1-2 предложения почему это выгодно/невыгодно",
  "why_good": ["причина 1", "причина 2"],
  "risks": ["риск 1", "риск 2"],
  "ai_score": 85,
  "recommendation": "buy",
  "confidence": 0.87
}}

recommendation должен быть "buy" (≥70 score), "maybe" (≥50), или "skip" (<50)."""

_INTENT_SYSTEM = """Ты — парсер поисковых запросов для маркетплейса.
Извлеки структурированные данные из запроса пользователя.
Отвечай строго в JSON."""

_INTENT_PROMPT = """Запрос пользователя: {text}

Верни JSON:
{{
  "query": "очищенный поисковый запрос",
  "keywords": ["ключевое1", "ключевое2"],
  "category": "электроника|авто|недвижимость|одежда|другое",
  "max_price": null,
  "min_price": null,
  "location": null,
  "condition": "any",
  "purpose": "self",
  "confidence": 0.95
}}

condition: "new"|"like_new"|"used"|"any"
purpose: "self"|"deal"|"resale" """

_RADAR_SYSTEM = """Ты — рыночный аналитик. Анализируй тренды цен на товары.
Давай краткие, точные комментарии на русском языке."""

_RADAR_PROMPT = """Данные по категориям за последние 2 недели:
{data}

Для каждой категории верни JSON массив:
[
  {{
    "category": "MacBook",
    "trend": "falling",
    "trend_pct": -7.2,
    "trend_emoji": "↓",
    "comment": "Цены падают — хороший момент для покупки",
    "hot_deals_count": 3
  }}
]
trend: "rising"|"falling"|"stable"
trend_emoji: "↑"|"↓"|"→"|"🔥" """


class OpenAIProvider(AIProvider):
    """OpenAI GPT-4o / GPT-4o-mini provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def name(self) -> str:
        return f"OpenAI ({self._model})"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self._api_key)
            except ImportError:
                log.error("openai package not installed. Run: pip install openai")
                return None
        return self._client

    async def _chat(self, system: str, user: str) -> Optional[str]:
        client = self._get_client()
        if not client:
            return None
        try:
            resp = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=800,
            )
            return resp.choices[0].message.content
        except Exception as e:
            log.warning("OpenAI API error: %s", e)
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
        prompt = _ANALYZE_PROMPT.format(
            title=title[:200],
            price=price,
            market_price=market_price,
            price_delta_pct=price_delta_pct,
            description=(description or "нет описания")[:500],
            seller_name=seller_name or "неизвестен",
            seller_rating=seller_rating or "нет рейтинга",
            images_count=images_count,
            similar_count=similar_count,
        )
        raw = await self._chat(_ANALYZE_SYSTEM, prompt)
        if not raw:
            return AIAnalysis(provider=self.name)
        try:
            data = json.loads(raw)
            return AIAnalysis(
                explanation=data.get("explanation", ""),
                why_good=data.get("why_good", []),
                risks=data.get("risks", []),
                ai_score=float(data.get("ai_score", 0)),
                recommendation=data.get("recommendation", "maybe"),
                confidence=float(data.get("confidence", 0)),
                provider=self.name,
            )
        except Exception as e:
            log.warning("Failed to parse OpenAI analysis: %s", e)
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
            f"Товар: {title}\n"
            f"Цена: {price:,.0f} ₽ (рынок: {market_price:,.0f} ₽)\n"
            f"Дешевле {cheaper_pct}% похожих объявлений из {similar_count}.\n"
            f"Экономия: {savings:,.0f} ₽ ({abs(price_delta_pct):.0f}%)\n\n"
            "Напиши объяснение в 2-3 предложения от имени AI агента. "
            "Начни с 'Я сравнил...'. Дружелюбно, понятно, без технических деталей. "
            "Верни JSON: {\"text\": \"твоё объяснение\"}"
        )
        raw = await self._chat(
            "Ты — AI помощник по покупкам. Объясняй просто и дружелюбно на русском.",
            prompt,
        )
        if not raw:
            return (
                f"Я сравнил {similar_count} похожих объявлений. "
                f"Средняя цена {market_price:,.0f} ₽. "
                f"Это предложение дешевле {cheaper_pct}% рынка."
            )
        try:
            return json.loads(raw).get("text", "")
        except Exception:
            return ""

    async def parse_intent(self, text: str) -> IntentParsed:
        prompt = _INTENT_PROMPT.format(text=text[:500])
        raw = await self._chat(_INTENT_SYSTEM, prompt)
        if not raw:
            return IntentParsed(query=text, keywords=text.split())
        try:
            data = json.loads(raw)
            return IntentParsed(
                query=data.get("query", text),
                keywords=data.get("keywords", text.split()),
                category=data.get("category", ""),
                max_price=data.get("max_price"),
                min_price=data.get("min_price"),
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
        data_str = json.dumps(categories_data, ensure_ascii=False, indent=2)[:2000]
        prompt = _RADAR_PROMPT.format(data=data_str)
        raw = await self._chat(_RADAR_SYSTEM, prompt)
        if not raw:
            return []
        try:
            # The model might wrap in an object; handle both array and {"items": [...]}
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else parsed.get("items", [])
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
            log.warning("Failed to parse radar: %s", e)
            return []
