"""Configuration for Market Agent."""

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
    data_dir: Path = Path("/opt/market_agent/data")
    db_path: Path = data_dir / "market_agent.db"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Collectors
    collector_interval_sec: int = 300  # 5 min between search cycles
    collector_avito_enabled: bool = True
    collector_youla_enabled: bool = True

    # Proxy (optional)
    proxy_url: Optional[str] = None

    # Playwright
    playwright_headless: bool = True
    playwright_slow_mo: int = 500  # ms

    # Analyzer
    price_lookback_days: int = 7  # how far back for market price calc
    min_listings_for_analysis: int = 5  # min similar listings to estimate price
    deal_score_threshold_buy: float = 70.0  # ≥70 → 🔥 immediate alert
    deal_score_threshold_maybe: float = 50.0  # ≥50 → standard alert

    # Dashboard
    dashboard_host: str = "0.0.0.0"
    dashboard_port: int = 8080

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


settings = Settings()
