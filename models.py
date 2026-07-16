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
    sources: list[str] = Field(default_factory=lambda: ["avito", "youla"])


class RawListing(BaseModel):
    """Raw listing from a collector — before analysis."""
    source: str  # 'avito', 'youla'
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
    score: float = 0.0  # 0-100
    factors: list[str] = Field(default_factory=list)


class DealScore(BaseModel):
    """Final deal evaluation."""
    score: float = 0.0  # 0-100
    market_price: float = 0.0
    price_delta_pct: float = 0.0  # how much below/above market
    risk_score: float = 0.0
    risk_factors: list[str] = Field(default_factory=list)
    recommendation: str = "skip"  # 'buy' | 'maybe' | 'skip'


class Alert(BaseModel):
    """Alert to send to user."""
    listing: RawListing
    deal: DealScore
    search_query: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
