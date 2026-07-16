"""PostgreSQL database provider for Market Agent."""

from __future__ import annotations

from typing import Optional
from models import SearchQuery, RawListing, DealScore, MarketRadarSnapshot
from database.base import BaseDatabase


class PostgresDatabase(BaseDatabase):
    """PostgreSQL implementation of the BaseDatabase (Placeholder for future SaaS expansion)."""

    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn
        # Placeholder initialization
        pass

    def init_schema(self) -> None:
        raise NotImplementedError("PostgreSQL implementation is planned for SaaS scale. Please use SQLite for now.")

    def upsert_user(self, telegram_id: int, username: Optional[str] = None,
                    first_name: Optional[str] = None) -> int:
        raise NotImplementedError()

    def get_user_by_telegram(self, telegram_id: int) -> Optional[dict]:
        raise NotImplementedError()

    def is_banned(self, telegram_id: int) -> bool:
        raise NotImplementedError()

    def is_admin(self, telegram_id: int) -> bool:
        raise NotImplementedError()

    def set_admin(self, telegram_id: int, is_admin: bool = True) -> None:
        raise NotImplementedError()

    def ban_user(self, telegram_id: int, banned: bool = True) -> None:
        raise NotImplementedError()

    def set_plan(self, telegram_id: int, plan: str, expires_at: Optional[str] = None) -> None:
        raise NotImplementedError()

    def mark_onboarded(self, telegram_id: int) -> None:
        raise NotImplementedError()

    def get_all_users(self, limit: int = 200) -> list[dict]:
        raise NotImplementedError()

    def get_admin_stats(self) -> dict:
        raise NotImplementedError()

    def create_search(self, search: SearchQuery) -> int:
        raise NotImplementedError()

    def get_active_searches(self) -> list[dict]:
        raise NotImplementedError()

    def get_user_searches(self, user_id: int) -> list[dict]:
        raise NotImplementedError()

    def deactivate_search(self, search_id: int) -> None:
        raise NotImplementedError()

    def activate_search(self, search_id: int) -> None:
        raise NotImplementedError()

    def get_search_stats(self, search_id: int) -> dict:
        raise NotImplementedError()

    def insert_listing(self, listing: RawListing) -> int:
        raise NotImplementedError()

    def listing_exists(self, url: str) -> bool:
        raise NotImplementedError()

    def get_listings_for_price_analysis(self, category: str, max_price: float, limit: int = 100) -> list[dict]:
        raise NotImplementedError()

    def save_analysis(self, listing_id: int, search_id: int, deal: DealScore) -> int:
        raise NotImplementedError()

    def save_alert(self, user_id: int, analysis_id: int) -> int:
        raise NotImplementedError()

    def get_recent_alerts(self, user_id: int, limit: int = 10) -> list[dict]:
        raise NotImplementedError()

    def create_opportunity(self, opportunity: dict) -> int:
        raise NotImplementedError()

    def update_opportunity(self, opp_id: int, **kwargs) -> None:
        raise NotImplementedError()

    def get_opportunity(self, opp_id: int) -> Optional[dict]:
        raise NotImplementedError()

    def find_matching_opportunity(self, user_id: int, title: str, price: float) -> Optional[dict]:
        raise NotImplementedError()

    def link_listing_to_opportunity(self, listing_id: int, opp_id: int) -> None:
        raise NotImplementedError()

    def get_user_settings_by_search_id(self, search_id: int) -> dict:
        raise NotImplementedError()

    def get_user_settings(self, user_id: int) -> dict:
        raise NotImplementedError()

    def upsert_user_settings(self, user_id: int, **kwargs) -> None:
        raise NotImplementedError()

    def save_find(self, user_id: int, listing_id: int, analysis_id: int, note: str = "") -> bool:
        raise NotImplementedError()

    def get_saved_finds(self, user_id: int, limit: int = 20) -> list[dict]:
        raise NotImplementedError()

    def remove_saved_find(self, user_id: int, listing_id: int) -> None:
        raise NotImplementedError()

    def save_market_radar(self, user_id: int, snapshot: MarketRadarSnapshot) -> None:
        raise NotImplementedError()

    def get_latest_radar(self, user_id: int, limit: int = 5) -> list[dict]:
        raise NotImplementedError()

    def get_ai_cache(self, cache_key: str) -> Optional[str]:
        raise NotImplementedError()

    def set_ai_cache(self, cache_key: str, provider: str, response: str) -> None:
        raise NotImplementedError()

    def get_stats(self) -> dict:
        raise NotImplementedError()

    def get_user_stats(self, user_id: int) -> dict:
        raise NotImplementedError()

    def close(self) -> None:
        pass
