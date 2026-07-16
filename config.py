"""Configuration for Market Agent v3 — SaaS Multi-User.

Only infrastructure settings here.
ALL user-specific settings (city, AI, thresholds, etc.) are stored in DB
and configured through the Telegram bot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Required ─────────────────────────────────────────────────────────────
    telegram_bot_token: str = ""

    # ── Admin ─────────────────────────────────────────────────────────────────
    # Your personal Telegram ID — get it from @userinfobot
    # This ID will have full admin access to the bot
    admin_telegram_id: int = 0

    # ── Database ─────────────────────────────────────────────────────────────
    db_path: Path = Path("data/market_agent.db")

    # ── Infrastructure (server-side, not per-user) ───────────────────────────
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8080
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    # ── Playwright (server-side) ──────────────────────────────────────────────
    playwright_headless: bool = True
    playwright_slow_mo: int = 1500       # ms to wait after page load

    # ── Proxy (server-side, optional) ─────────────────────────────────────────
    proxy_url: Optional[str] = None

    # ── Collectors (infrastructure toggle, server-side) ──────────────────────
    collector_avito_enabled: bool = True
    collector_youla_enabled: bool = True
    collector_interval_sec: int = 30     # loop sleep in seconds for multi-user daemon

    # ── Price analysis (infrastructure settings) ──────────────────────────────
    min_listings_for_analysis: int = 5   # min similar listings to estimate price

    # ── Global AI fallback (used if user has no AI configured) ───────────────
    # Leave empty if you want users to configure their own AI
    wormsoft_api_key: str = ""
    wormsoft_base_url: str = "https://ai.wormsoft.ru/api/gpt"
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    ai_provider: str = ""               # global fallback provider
    ai_model: str = ""                  # global fallback model

    @field_validator("admin_telegram_id", "dashboard_port", "playwright_slow_mo", "collector_interval_sec", "min_listings_for_analysis", mode="before")
    @classmethod
    def empty_str_to_numeric_default(cls, v, info):
        if v == "" or v is None:
            defaults = {
                "admin_telegram_id": 0,
                "dashboard_port": 8080,
                "playwright_slow_mo": 1500,
                "collector_interval_sec": 30,
                "min_listings_for_analysis": 5,
            }
            return defaults.get(info.field_name, 0)
        return int(v)

    @field_validator("playwright_headless", "collector_avito_enabled", "collector_youla_enabled", mode="before")
    @classmethod
    def empty_str_to_bool_default(cls, v, info):
        if v == "" or v is None:
            return True
        if str(v).lower() in ("false", "0", "no", "n"):
            return False
        return True

    def is_ai_configured(self) -> bool:
        return bool(
            self.wormsoft_api_key
            or self.openai_api_key
            or self.gemini_api_key
            or self.anthropic_api_key
            or self.ai_provider
        )

    def is_admin(self, telegram_id: int) -> bool:
        return self.admin_telegram_id != 0 and telegram_id == self.admin_telegram_id


settings = Settings()

