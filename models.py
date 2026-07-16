"""Pydantic models for Market Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SearchQuery(BaseModel):
    """A user's search request — structured filters."""
    user_id: int
    query: str
    category: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    max_price: Optional[float] = None
    min_price: Optional[float] = None
    location: Optional[str] = None
    condition: str = "any"                  # "new" | "like_new" | "used" | "any"
    purpose: str = "self"                   # "self" | "deal" | "resale"
    sources: list[str] = Field(default_factory=lambda: ["avito", "youla"])


class RawListing(BaseModel):
    """Raw listing from a collector — before analysis."""
    source: str                             # 'avito', 'youla'
    source_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    price: float
    currency: str = "RUB"
    location: Optional[str] = None
    url: str
    images: list[str] = Field(default_factory=list)
    seller_name: Optional[str] = None
    seller_rating: Optional[float] = None
    seller_deals_count: Optional[int] = None
    seller_registered_at: Optional[str] = None
    parsed_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class PriceStats(BaseModel):
    """Market price statistics from similar listings."""
    median: float = 0.0
    mean: float = 0.0
    p10: float = 0.0
    p25: float = 0.0
    p75: float = 0.0
    p90: float = 0.0
    std: float = 0.0
    sample_size: int = 0


class RiskScore(BaseModel):
    """Risk assessment for a listing."""
    score: float = 0.0                      # 0-100
    factors: list[str] = Field(default_factory=list)


class DealScore(BaseModel):
    """Final deal evaluation (heuristic + optional AI)."""
    score: float = 0.0                      # 0-100
    market_price: float = 0.0
    price_delta_pct: float = 0.0            # how much below/above market
    risk_score: float = 0.0
    risk_factors: list[str] = Field(default_factory=list)
    recommendation: str = "skip"           # 'buy' | 'maybe' | 'skip'

    # AI layer (populated when AI is enabled)
    ai_score: Optional[float] = None
    ai_explanation: Optional[str] = None
    ai_why_good: list[str] = Field(default_factory=list)
    ai_risks: list[str] = Field(default_factory=list)
    ai_provider: Optional[str] = None


class Alert(BaseModel):
    """Alert to send to user."""
    listing: RawListing
    deal: DealScore
    search_query: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ── New models for extended features ──────────────────────────────────────────

class HunterSettings(BaseModel):
    """Per-user Hunter Mode configuration."""
    enabled: bool = False
    check_interval_sec: int = 300           # 5 min default
    min_savings_pct: float = 10.0           # minimum savings % to alert
    min_deal_score: float = 50.0            # minimum deal score to alert


class UserSettings(BaseModel):
    """Per-user settings stored in DB."""
    user_id: int
    hunter: HunterSettings = Field(default_factory=HunterSettings)

    # AI provider override (empty = use global config)
    ai_provider: str = ""                   # "openai" | "gemini" | "anthropic" | ""
    ai_api_key: str = ""
    ai_model: str = ""

    # Notifications
    notifications_enabled: bool = True
    notify_on_buy: bool = True              # score >= 70
    notify_on_maybe: bool = False           # score >= 50

    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SavedFind(BaseModel):
    """A listing saved by the user for later review."""
    user_id: int
    listing_id: int
    analysis_id: int
    note: Optional[str] = None
    saved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class MarketRadarSnapshot(BaseModel):
    """Market radar data for a category at a point in time."""
    category: str
    avg_price: float = 0.0
    median_price: float = 0.0
    sample_size: int = 0
    trend: str = "stable"                  # "rising" | "falling" | "stable"
    trend_pct: float = 0.0
    trend_emoji: str = "→"
    ai_comment: str = ""
    hot_deals_count: int = 0
    snapshot_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
