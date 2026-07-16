"""Google Gemini provider for Market Agent AI analysis."""

from __future__ import annotations

import json
import logging
from typing import Optional

from ai.base import AIProvider, AIAnalysis, IntentParsed, MarketRadarItem

log = logging.getLogger("market_agent.ai.gemini")

_ANALYZE_PROMPT = """Ты — AI аналитик рынка подержанных товаров (Авито, Юла).

Объявление:
Название: {title}
Цена: {price} ₽
Средняя цена рынка: {market_price} ₽
Отклонение от рынка: {price_delta_pct:+.1f}%
Описание: {description}
Продавец: {seller_name} (рейтинг: {seller_rating})
Фотографий: {images_count}
Похожих объявлений: {similar_count}

Верни ТОЛЬКО JSON (без markdown):
{{
  "explanation": "краткое объяснение 1-2 предложения",
  "why_good": ["причина 1", "причина 2"],
  "risks": ["риск 1"],
  "ai_score": 85,
  "recommendation": "buy",
  "confidence": 0.87
}}"""

_INTENT_PROMPT = """Ты — парсер поисковых запросов. Извлеки данные из запроса.
Запрос: {text}

Верни ТОЛЬКО JSON:
{{
  "query": "очищенный запрос",
  "keywords": ["слово1", "слово2"],
  "category": "электроника",
  "max_price": null,
  "location": null,
  "condition": "any",
  "purpose": "self",
  "confidence": 0.95
}}"""


class GeminiProvider(AIProvider):
    """Google Gemini 1.5 Flash / Pro provider (cost-effective choice)."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self._api_key = api_key
        self._model = model
        self._client = None

    @property
    def name(self) -> str:
        return f"Gemini ({self._model})"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    def _get_client(self):
        if self._client is None:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self._api_key)
                self._client = genai.GenerativeModel(
                    self._model,
                    generation_config={"response_mime_type": "application/json"},
                )
            except ImportError:
                log.error(
                    "google-generativeai not installed. Run: pip install google-generativeai"
                )
                return None
        return self._client

    async def _generate(self, prompt: str) -> Optional[str]:
        client = self._get_client()
        if not client:
            return None
        try:
            # Gemini SDK is sync — run in executor for async compatibility
            import asyncio
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None, lambda: client.generate_content(prompt)
            )
            return resp.text
        except Exception as e:
            log.warning("Gemini API error: %s", e)
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
        raw = await self._generate(prompt)
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
            log.warning("Failed to parse Gemini analysis: %s", e)
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
            f"Экономия: {savings:,.0f} ₽.\n\n"
            "Напиши объяснение в 2-3 предложения от имени AI агента, начиная с 'Я сравнил...'. "
            "Дружелюбно и понятно. JSON: {\"text\": \"объяснение\"}"
        )
        raw = await self._generate(prompt)
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
        raw = await self._generate(prompt)
        if not raw:
            return IntentParsed(query=text, keywords=text.split())
        try:
            data = json.loads(raw)
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
            f"Данные по категориям товаров за 2 недели:\n{data_str}\n\n"
            "Для каждой категории определи тренд цен и дай краткий комментарий на русском. "
            "JSON массив: [{\"category\": \"...\", \"trend\": \"falling\", "
            "\"trend_pct\": -7.2, \"trend_emoji\": \"↓\", "
            "\"comment\": \"...\", \"hot_deals_count\": 3}]"
        )
        raw = await self._generate(prompt)
        if not raw:
            return []
        try:
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
            log.warning("Failed to parse Gemini radar: %s", e)
            return []
