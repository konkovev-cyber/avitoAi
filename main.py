#!/usr/bin/env python3
"""
Market Agent v2 — Personal AI Marketplace Intelligence Platform.

Usage:
    python main.py init            # Initialize database
    python main.py collect         # Run collector daemon
    python main.py bot             # Run Telegram bot
    python main.py dashboard       # Run web dashboard
    python main.py status          # Show system status
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from config import settings
from database.db import Database

log = logging.getLogger("market_agent")


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=settings.log_format,
    )


def cmd_init():
    """Initialize database schema."""
    db = Database()
    db.init_schema()
    print(f"✅ Database initialized: {settings.db_path}")
    print("   Tables: users, searches, listings, analysis, alerts,")
    print("           user_settings, saved_finds, market_radar, ai_cache")

    if settings.is_ai_configured():
        from ai.factory import get_ai_provider
        prov = get_ai_provider()
        print(f"🤖 AI provider: {prov.name if prov else 'none'}")
    else:
        print("⚙️  AI: not configured (heuristics-only mode)")
        print("   To enable AI: set MA_OPENAI_API_KEY / MA_GEMINI_API_KEY in .env")


def cmd_status():
    """Show system status."""
    db = Database()
    db.init_schema()
    stats = db.get_stats()

    print("\n🤖 Market Agent v2 — Status")
    print("━" * 40)
    print(f"  Listings:  {stats['listings']}")
    print(f"  Analyses:  {stats['analyses']}")
    print(f"  Alerts:    {stats['alerts']}")
    print(f"  Sources:   {stats.get('by_source', {})}")
    print()
    print(f"  Bot token: {'✅ set' if settings.telegram_bot_token else '❌ missing'}")
    print(f"  AI:        {'✅ ' + settings.ai_provider if settings.is_ai_configured() else '⚙️  heuristics only'}")
    print(f"  DB path:   {settings.db_path}")
    print()


def cmd_collect():
    """Run collector daemon."""
    from collector.scheduler import Scheduler

    db = Database()
    db.init_schema()

    scheduler = Scheduler(db)
    try:
        asyncio.run(scheduler.run())
    except KeyboardInterrupt:
        log.info("Collector stopped")


def cmd_bot():
    """Run Telegram bot daemon (also runs collector in background)."""
    from bot.telegram import MarketAgentBot, DB

    DB.init_schema()
    bot = MarketAgentBot(DB)

    # Optional: run collector alongside bot in same process
    # For production, run them as separate services
    try:
        bot.start()
    except ValueError as e:
        log.error("Bot error: %s", e)
        sys.exit(1)


def cmd_dashboard():
    """Run web dashboard."""
    try:
        import uvicorn
        from dashboard.app import app
        uvicorn.run(
            app,
            host=settings.dashboard_host,
            port=settings.dashboard_port,
            log_level=settings.log_level.lower(),
        )
    except ImportError:
        log.error("Dashboard dependencies not installed")
        sys.exit(1)


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Market Agent v2 — AI Marketplace Intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="Initialize database")
    sub.add_parser("status", help="Show system status")
    sub.add_parser("collect", help="Run collector daemon")
    sub.add_parser("bot", help="Run Telegram bot")
    sub.add_parser("dashboard", help="Run web dashboard")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "status": cmd_status,
        "collect": cmd_collect,
        "bot": cmd_bot,
        "dashboard": cmd_dashboard,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
