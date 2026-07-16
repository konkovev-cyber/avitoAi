"""WormSoft AI provider for Market Agent.

Документация: https://ai.wormsoft.ru/docs
Base URL:     https://ai.wormsoft.ru/api/gpt  (алиасы: /gpt/v1, /gpt/v1/v1)
Auth:         Authorization: Bearer API_KEY
Формат:       OpenAI-compatible (chat/completions)

Модели:
  wormsoft/agent/low    — быстрая и дешёвая
  wormsoft/agent/medium — точнее, дольше
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from ai.base import AIProvider, AIAnalysis, IntentParsed, MarketRadarItem

log = logging.getLogger("market_agent.ai.wormsoft")

WORMSOFT_BASE_URL = "https://ai.wormsoft.ru/api/gpt"
WORMSOFT_CHAT_ENDPOINT = "/v1/chat/completions"

_ANALYZE_SYSTEM = (
    "Ты — AI аналитик рынка подержанных товаров (Авито, Юла). "
    "Оцени объявление и дай рекомендацию. Отвечай строго в JSON на русском языке."
)

_ANALYZE_PROMPT = """Объявление:
Название: {title}
Цена: {price} ₽
Средняя цена рынка: {market_price} ₽
Отклонение: {price_delta_pct:+.1f}%
Описание: {description}
Продавец: {seller_name} (рейтинг: {seller_rating})
Фото: {images_count} шт. | Похожих объявлений: {similar_count}

JSON ответ:
{{
  "explanation": "1-2 предложения почему выгодно или нет",
  "why_good": ["причина 1", "причина 2"],
  "risks": ["риск 1"],
  "ai_score": 85,
  "recommendation": "buy",
  "confidence": 0.87
}}
recommendation: "buy" (score>=70) | "maybe" (score>=50) | "skip" (<50)"""

_INTENT_SYSTEM = "Ты — парсер поисковых запросов маркетплейса. Отвечай только JSON."

_INTENT_PROMPT = """Запрос пользователя: {text}

{{
  "query": "очищенный запрос",
  "keywords": ["слово1", "слово2"],
  "category": "электроника",
  "max_price": null,
  "location": null,
  "condition": "any",
  "purpose": "self",
  "confidence": 0.95
}}
condition: "new"|"like_new"|"used"|"any"
purpose: "self"|"deal"|"resale" """

_RADAR_SYSTEM = "Ты — рыночный аналитик. Отвечай только JSON на русском языке."

_RADAR_PROMPT = """Данные по категориям товаров за 2 недели:
{data}

Для каждой категории: тренд, emoji, комментарий.
JSON массив:
[{{"category":"...", "trend":"falling", "trend_pct":-7.2, "trend_emoji":"↓", "comment":"...", "hot_deals_count":3}}]
trend: "rising"|"falling"|"stable"
trend_emoji: "↑"|"↓"|"→"|"🔥" """


class WormSoftProvider(AIProvider):
    """WormSoft AI — агентские модели по себестоимости.

    OpenAI-совместимый API, поддерживает:
      wormsoft/agent/low    — быстрая/дешёвая
      wormsoft/agent/medium — точнее
    """

    def __init__(
        self,
        api_key: str,
        model: str = "wormsoft/agent/low",
        base_url: str = WORMSOFT_BASE_URL,
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return f"WormSoft ({self._model})"

    @property
    def is_available(self) -> bool:
        return bool(self._api_key)

    # ── HTTP ──────────────────────────────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def _chat(self, system: str, user: str, max_tokens: int = 1000) -> Optional[str]:
        """POST to /v1/chat/completions — OpenAI-compatible."""
        client = self._get_client()
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
            "max_tokens": max_tokens,
        }
        try:
            resp = await client.post(WORMSOFT_CHAT_ENDPOINT, json=payload)
            resp.raise_for_status()
            data = resp.json()

            # Standard OpenAI response
            choices = data.get("choices")
            if choices and len(choices) > 0:
                msg = choices[0].get("message", {})
                return msg.get("content", "")

            # Fallback for alternative response shapes
            for key in ("content", "text", "response", "output"):
                if key in data:
                    return str(data[key])

            log.warning("WormSoft: unexpected response keys: %s", list(data.keys()))
            return None

        except httpx.HTTPStatusError as e:
            log.warning(
                "WormSoft HTTP %s: %s — body: %s",
                e.response.status_code, e.request.url,
                e.response.text[:300],
            )
            return None
        except httpx.TimeoutException:
            log.warning("WormSoft request timed out")
            return None
        except Exception as e:
            log.warning("WormSoft unexpected error: %s", e)
            return None

    # ── JSON helpers ──────────────────────────────────────────────────────────

    def _parse_json(self, text: str) -> Optional[dict | list]:
        """Extract JSON from response (handles prose around JSON)."""
        if not text:
            return None
        text = text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(
                l for l in lines
                if not l.strip().startswith("```")
            ).strip()
        # Direct parse
        try:
            return json.loads(text)
        except Exception:
            pass
        # Find embedded JSON object
        for s_char, e_char in [("{", "}"), ("[", "]")]:
            start = text.find(s_char)
            end = text.rfind(e_char) + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except Exception:
                    pass
        return None

    # ── AIProvider interface ───────────────────────────────────────────────────

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
        data = self._parse_json(raw)
        if not isinstance(data, dict):
            log.warning("WormSoft analyze: non-dict response: %s", str(raw)[:200])
            return AIAnalysis(provider=self.name)
        try:
            return AIAnalysis(
                explanation=data.get("explanation", ""),
                why_good=data.get("why_good", []),
                risks=data.get("risks", []),
                ai_score=float(data.get("ai_score", 0)),
                recommendation=data.get("recommendation", "maybe"),
                confidence=float(data.get("confidence", 0.8)),
                provider=self.name,
            )
        except Exception as e:
            log.warning("WormSoft: failed to map analysis: %s", e)
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
            f"Дешевле {cheaper_pct}% из {similar_count} похожих объявлений. "
            f"Экономия: {savings:,.0f} ₽ ({abs(price_delta_pct):.0f}%).\n\n"
            "Напиши объяснение 2-3 предложения от имени AI-агента, начни с 'Я сравнил...'. "
            "Дружелюбно, по-русски, без технических деталей. "
            'JSON: {"text": "объяснение"}'
        )
        raw = await self._chat(
            "Ты AI помощник по покупкам. Отвечай только JSON на русском языке.",
            prompt,
            max_tokens=300,
        )
        if not raw:
            return (
                f"Я сравнил {similar_count} похожих объявлений. "
                f"Средняя цена {market_price:,.0f} ₽. "
                f"Это предложение дешевле {cheaper_pct}% рынка."
            )
        data = self._parse_json(raw)
        if isinstance(data, dict) and data.get("text"):
            return data["text"]
        return ""

    async def parse_intent(self, text: str) -> IntentParsed:
        prompt = _INTENT_PROMPT.format(text=text[:500])
        raw = await self._chat(_INTENT_SYSTEM, prompt, max_tokens=400)
        if not raw:
            return IntentParsed(query=text, keywords=text.split())
        data = self._parse_json(raw)
        if not isinstance(data, dict):
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
        prompt = _RADAR_PROMPT.format(data=data_str)
        raw = await self._chat(_RADAR_SYSTEM, prompt, max_tokens=800)
        if not raw:
            return []
        parsed = self._parse_json(raw)
        if not parsed:
            return []
        items = parsed if isinstance(parsed, list) else parsed.get("items", [])
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
                if isinstance(i, dict) and i.get("category")
            ]
        except Exception as e:
            log.warning("WormSoft radar parse error: %s", e)
            return []

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
