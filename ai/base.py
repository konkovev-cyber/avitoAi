"""Abstract AI provider interface for Market Agent.

All AI providers implement AIProvider. The system works without AI (returns None)
so users without API keys still get full functionality via heuristics only.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AIAnalysis:
    """Result of AI analysis for a single listing."""

    explanation: str = ""                   # "Я сравнил 86 объявлений. Цена ниже 90% рынка."
    why_good: list[str] = field(default_factory=list)   # ["цена ниже рынка", "хороший продавец"]
    risks: list[str] = field(default_factory=list)      # ["нет чека", "новый аккаунт"]
    ai_score: float = 0.0                   # 0-100, AI's own confidence
    recommendation: str = "maybe"          # "buy" | "maybe" | "skip"
    confidence: float = 0.0                # 0-1, how confident the AI is
    provider: str = ""                     # which provider generated this


@dataclass
class MarketRadarItem:
    """AI-generated market radar report for one category."""

    category: str
    trend: str = "stable"                  # "rising" | "falling" | "stable"
    trend_pct: float = 0.0                 # +7.0 means +7% price change
    trend_emoji: str = "→"                 # "↑" | "↓" | "→" | "🔥"
    comment: str = ""                      # "Цены падают 7% — хороший момент для покупки"
    hot_deals_count: int = 0               # number of hot deals found this week
    avg_price: float = 0.0
    sample_size: int = 0


@dataclass
class IntentParsed:
    """Result of AI intent parsing from user's natural text."""

    query: str = ""
    keywords: list[str] = field(default_factory=list)
    category: str = ""
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    location: Optional[str] = None
    condition: str = "any"                 # "new" | "like_new" | "used" | "any"
    purpose: str = "self"                  # "self" | "deal" | "resale"
    confidence: float = 1.0


class AIProvider(ABC):
    """Abstract interface for all AI providers.

    Implementations: OpenAIProvider, GeminiProvider, AnthropicProvider.
    Every method is safe — catches all exceptions and returns a fallback.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging and UI."""
        ...

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether this provider is configured and ready."""
        ...

    @abstractmethod
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
        """Analyze a single listing and return AI assessment."""
        ...

    @abstractmethod
    async def explain_deal(
        self,
        title: str,
        price: float,
        market_price: float,
        similar_count: int,
        price_delta_pct: float,
        percentile_position: float,
    ) -> str:
        """Generate a human-friendly explanation of why this is a good deal."""
        ...

    @abstractmethod
    async def parse_intent(self, text: str) -> IntentParsed:
        """Parse natural language search intent from user message."""
        ...

    @abstractmethod
    async def generate_market_radar(
        self, categories_data: list[dict]
    ) -> list[MarketRadarItem]:
        """Generate Market Radar report for given categories."""
        ...
