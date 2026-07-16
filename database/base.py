"""Abstract Base Class for Database Providers in Market Agent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Any
from models import SearchQuery, RawListing, DealScore, MarketRadarSnapshot


class BaseDatabase(ABC):
    """Abstract interface defining all required database operations."""

    @abstractmethod
    def init_schema(self) -> None:
        """Initialize database schema/migrations."""
        pass

    # ── Users ────────────────────────────────────────────────────────────────

    @abstractmethod
    def upsert_user(self, telegram_id: int, username: Optional[str] = None,
                    first_name: Optional[str] = None) -> int:
        """Create or update user in database. Returns database user ID."""
        pass

    @abstractmethod
    def get_user_by_telegram(self, telegram_id: int) -> Optional[dict]:
        """Fetch user by Telegram ID."""
        pass

    @abstractmethod
    def is_banned(self, telegram_id: int) -> bool:
        """Check if user is banned."""
        pass

    @abstractmethod
    def is_admin(self, telegram_id: int) -> bool:
        """Check if user is admin."""
        pass

    @abstractmethod
    def set_admin(self, telegram_id: int, is_admin: bool = True) -> None:
        """Grant or revoke admin privileges."""
        pass

    @abstractmethod
    def ban_user(self, telegram_id: int, banned: bool = True) -> None:
        """Ban or unban user."""
        pass

    @abstractmethod
    def set_plan(self, telegram_id: int, plan: str, expires_at: Optional[str] = None) -> None:
        """Update user subscription plan."""
        pass

    @abstractmethod
    def mark_onboarded(self, telegram_id: int) -> None:
        """Mark user onboarding as completed."""
        pass

    @abstractmethod
    def get_all_users(self, limit: int = 200) -> list[dict]:
        """Fetch list of all users."""
        pass

    @abstractmethod
    def get_admin_stats(self) -> dict:
        """Fetch administrative dashboard stats."""
        pass

    # ── Searches ─────────────────────────────────────────────────────────────

    @abstractmethod
    def create_search(self, search: SearchQuery) -> int:
        """Create new active search query."""
        pass

    @abstractmethod
    def get_active_searches(self) -> list[dict]:
        """Fetch all active searches system-wide."""
        pass

    @abstractmethod
    def get_user_searches(self, user_id: int) -> list[dict]:
        """Fetch all searches for a specific user ID."""
        pass

    @abstractmethod
    def deactivate_search(self, search_id: int) -> None:
        """Deactivate search query."""
        pass

    @abstractmethod
    def activate_search(self, search_id: int) -> None:
        """Activate search query."""
        pass

    @abstractmethod
    def get_search_stats(self, search_id: int) -> dict:
        """Get stats for a search query."""
        pass

    # ── Listings ─────────────────────────────────────────────────────────────

    @abstractmethod
    def insert_listing(self, listing: RawListing) -> int:
        """Insert newly scraped listing."""
        pass

    @abstractmethod
    def listing_exists(self, url: str) -> bool:
        """Check if listing with given URL exists."""
        pass

    @abstractmethod
    def get_listings_for_price_analysis(self, category: str, max_price: float, limit: int = 100) -> list[dict]:
        """Get similar listings for price estimation."""
        pass

    # ── Analysis ─────────────────────────────────────────────────────────────

    @abstractmethod
    def save_analysis(self, listing_id: int, search_id: int, deal: DealScore) -> int:
        """Save deal evaluation result."""
        pass

    @abstractmethod
    def save_alert(self, user_id: int, analysis_id: int) -> int:
        """Record sent alert."""
        pass

    @abstractmethod
    def get_recent_alerts(self, user_id: int, limit: int = 10) -> list[dict]:
        """Get recent alerts sent to user."""
        pass

    # ── Opportunities ─────────────────────────────────────────────────────────

    @abstractmethod
    def create_opportunity(self, opportunity: dict) -> int:
        """Create a new opportunity."""
        pass

    @abstractmethod
    def update_opportunity(self, opp_id: int, **kwargs) -> None:
        """Update opportunity metrics."""
        pass

    @abstractmethod
    def get_opportunity(self, opp_id: int) -> Optional[dict]:
        """Get opportunity details."""
        pass

    @abstractmethod
    def find_matching_opportunity(self, user_id: int, title: str, price: float) -> Optional[dict]:
        """Find existing matching opportunity by user and similar title/price."""
        pass

    @abstractmethod
    def link_listing_to_opportunity(self, listing_id: int, opp_id: int) -> None:
        """Link a listing to an opportunity."""
        pass

    # ── User Settings ─────────────────────────────────────────────────────────

    @abstractmethod
    def get_user_settings_by_search_id(self, search_id: int) -> dict:
        """Get user settings associated with search query ID."""
        pass

    @abstractmethod
    def get_user_settings(self, user_id: int) -> dict:
        """Get user settings associated with user ID."""
        pass

    @abstractmethod
    def upsert_user_settings(self, user_id: int, **kwargs) -> None:
        """Upsert user settings parameters."""
        pass

    # ── Saved Finds ───────────────────────────────────────────────────────────

    @abstractmethod
    def save_find(self, user_id: int, listing_id: int, analysis_id: int, note: str = "") -> bool:
        """Save a finding for user."""
        pass

    @abstractmethod
    def get_saved_finds(self, user_id: int, limit: int = 20) -> list[dict]:
        """Get all saved findings for user."""
        pass

    @abstractmethod
    def remove_saved_find(self, user_id: int, listing_id: int) -> None:
        """Remove a finding from user saved list."""
        pass

    # ── Market Radar ──────────────────────────────────────────────────────────

    @abstractmethod
    def save_market_radar(self, user_id: int, snapshot: MarketRadarSnapshot) -> None:
        """Save market radar snapshot."""
        pass

    @abstractmethod
    def get_latest_radar(self, user_id: int, limit: int = 5) -> list[dict]:
        """Get latest market radar snapshots for user."""
        pass

    # ── AI Cache ─────────────────────────────────────────────────────────────

    @abstractmethod
    def get_ai_cache(self, cache_key: str) -> Optional[str]:
        """Get cached AI response by key if not expired."""
        pass

    @abstractmethod
    def set_ai_cache(self, cache_key: str, provider: str, response: str) -> None:
        """Store AI response in cache."""
        pass

    # ── Stats ─────────────────────────────────────────────────────────────────

    @abstractmethod
    def get_stats(self) -> dict:
        """Get global database stats."""
        pass

    @abstractmethod
    def get_user_stats(self, user_id: int) -> dict:
        """Get stats for a specific user ID."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connection."""
        pass
