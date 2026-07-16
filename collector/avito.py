"""Avito collector — Playwright-based."""

from __future__ import annotations

import logging
import re
import time
from typing import Optional
from urllib.parse import quote

from config import settings
from models import RawListing, SearchQuery
from .base import BaseCollector

log = logging.getLogger("market_agent.collector.avito")


class AvitoCollector(BaseCollector):
    """Collects listings from Avito.ru using Playwright."""

    BASE_URL = "https://www.avito.ru"

    def __init__(self, proxy_url: Optional[str] = None):
        super().__init__(proxy_url)
        self._browser = None
        self._context = None
        self._page = None

    async def _ensure_browser(self):
        if self._browser is not None:
            return
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        launch_kwargs = {
            "headless": settings.playwright_headless,
        }
        if self.proxy_url:
            launch_kwargs["proxy"] = {"server": self.proxy_url}

        self._browser = await self._pw.chromium.launch(**launch_kwargs)
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
        )
        self._page = await self._context.new_page()
        log.info("Browser launched")

    async def search(self, query: SearchQuery) -> list[RawListing]:
        await self._ensure_browser()
        url = self._make_search_url(query)
        self.log(f"Searching: {url}")

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._page.wait_for_timeout(2000)  # let JS render

            # Try to find listing items
            items = await self._page.query_selector_all(
                '[data-marker="item"], [itemtype="http://schema.org/Product"]'
            )
            if not items:
                # Fallback: look for any listing cards
                items = await self._page.query_selector_all(
                    ".iva-item-root, .items-item, article"
                )

            self.log(f"Found {len(items)} items on page")
            results = []
            for item in items[:30]:  # limit to first 30
                try:
                    listing = await self._parse_item(item)
                    if listing:
                        results.append(listing)
                except Exception as e:
                    self.log(f"Parse error: {e}", "warning")
            return results

        except Exception as e:
            self.log(f"Search error: {e}", "error")
            return []

    async def _parse_item(self, item) -> Optional[RawListing]:
        """Parse a single listing card."""
        try:
            # Title and URL
            link = await item.query_selector("a[href]")
            if not link:
                return None
            href = await link.get_attribute("href") or ""
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href

            title_el = await link.query_selector(
                "h3, [itemprop='name'], .title, [class*='title']"
            )
            title = ""
            if title_el:
                title = (await title_el.inner_text()).strip()
            if not title:
                title = (await link.inner_text()).strip()[:200]

            # Price
            price = await self._extract_price(item)

            # Location
            loc = await self._extract_text(item, "[class*='address'], [class*='location']")

            # Seller
            seller = await self._extract_text(item, "[class*='seller'], [data-marker='seller']")

            return RawListing(
                source="avito",
                title=title[:500],
                price=price,
                location=loc,
                url=url,
                seller_name=seller,
            )
        except Exception as e:
            self.log(f"Item parse error: {e}", "warning")
            return None

    async def _extract_price(self, item) -> float:
        """Extract price from a listing card."""
        price_el = await item.query_selector(
            "[itemprop='price'], [class*='price'], [data-marker='price']"
        )
        if not price_el:
            return 0.0
        text = (await price_el.inner_text()).strip()
        # Extract digits
        nums = re.findall(r"[\d\s]+", text)
        clean = "".join(nums).strip()
        try:
            return float(clean.replace(" ", "")) if clean else 0.0
        except ValueError:
            return 0.0

    @staticmethod
    async def _extract_text(parent, selector: str) -> Optional[str]:
        el = await parent.query_selector(selector)
        if el:
            return (await el.inner_text()).strip()
        return None

    def _make_search_url(self, query: SearchQuery) -> str:
        parts = [self.BASE_URL, "moskva"]  # default location
        if query.category:
            parts.append(f"q={quote(query.query)}")
        else:
            parts.append(f"q={quote(query.query)}")
        params = []
        if query.max_price:
            params.append(f"p={int(query.max_price)}")
        url = f"{'/'.join(parts)}?{'&'.join(params)}" if params else "/".join(parts)
        return url

    async def close(self):
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_pw") and self._pw:
            await self._pw.stop()
        self.log("Closed")
