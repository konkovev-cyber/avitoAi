#!/usr/bin/env python3
"""
Market Agent — Personal Marketplace Intelligence Agent.

Usage:
    python3 main.py init            # Initialize database
    python3 main.py collect         # Run collector daemon
    python3 main.py bot             # Run Telegram bot daemon
    python3 main.py dashboard       # Run web dashboard
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
    print(f"Database initialized at {settings.db_path}")
    print(f"Tables: users, searches, listings, analysis, alerts")


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
    """Run Telegram bot daemon."""
    from bot.telegram import DB, MarketAgentBot

    DB.init_schema()
    bot = MarketAgentBot(DB)
    bot.start()


def cmd_dashboard():
    """Run web dashboard."""
    import uvicorn

    from dashboard.app import app

    uvicorn.run(
        app,
        host=settings.dashboard_host,
        port=settings.dashboard_port,
        log_level=settings.log_level.lower(),
    )


def main():
    setup_logging()

    parser = argparse.ArgumentParser(description="Market Agent")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Initialize database")
    sub.add_parser("collect", help="Run collector daemon")
    sub.add_parser("bot", help="Run Telegram bot daemon")
    sub.add_parser("dashboard", help="Run web dashboard")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "collect": cmd_collect,
        "bot": cmd_bot,
        "dashboard": cmd_dashboard,
    }

    commands[args.command]()


if __name__ == "__main__":
    main()
