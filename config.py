"""Configuration for Market Agent v2."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MA_",
    )

    # Project paths
    data_dir: Path = Path("data")
    db_path: Path = Path("data/market_agent.db")

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Collectors
    collector_interval_sec: int = 300        # 5 min between search cycles
    collector_avito_enabled: bool = True
    collector_youla_enabled: bool = True

    # Proxy (optional)
    proxy_url: Optional[str] = None

    # Playwright
    playwright_headless: bool = True
    playwright_slow_mo: int = 500            # ms

    # Analyzer
    price_lookback_days: int = 7             # how far back for market price calc
    min_listings_for_analysis: int = 5       # min similar listings to estimate price
    deal_score_threshold_buy: float = 70.0   # ≥70 → 🔥 immediate alert
    deal_score_threshold_maybe: float = 50.0 # ≥50 → standard alert

    # ── AI (all optional — system works without AI) ────────────────────────────
    ai_provider: str = ""                    # "wormsoft" | "openai" | "gemini" | "anthropic" | ""
    ai_model: str = ""                       # specific model override (empty = provider default)
    ai_enabled: bool = False                 # explicit enable flag

    # WormSoft (рекомендуется — агентские модели по себестоимости)
    wormsoft_api_key: str = ""
    wormsoft_base_url: str = "https://ai.wormsoft.ru/api/gpt"

    # Другие провайдеры
    openai_api_key: str = ""
    gemini_api_key: str = ""
    anthropic_api_key: str = ""

    # ── Dashboard ─────────────────────────────────────────────────────────────
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8080

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    def is_ai_configured(self) -> bool:
        """Returns True if at least one AI provider key is set."""
        return bool(
            self.wormsoft_api_key
            or self.openai_api_key
            or self.gemini_api_key
            or self.anthropic_api_key
        )


settings = Settings()
