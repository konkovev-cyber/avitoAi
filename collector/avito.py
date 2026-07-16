"""Avito collector — Playwright-based scraper.

Supports all SearchQuery fields:
  - query / keywords
  - location (city → avito city slug)
  - max_price / min_price
  - condition (new / like_new / used / any)
  - category
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import quote, urlencode

from config import settings
from models import RawListing, SearchQuery
from .base import BaseCollector

log = logging.getLogger("market_agent.collector.avito")

# Avito city slugs (ru → slug)
CITY_SLUGS: dict[str, str] = {
    "москва": "moskva",
    "санкт-петербург": "sankt-peterburg",
    "спб": "sankt-peterburg",
    "питер": "sankt-peterburg",
    "екатеринбург": "ekaterinburg",
    "новосибирск": "novosibirsk",
    "казань": "kazan",
    "нижний новгород": "nizhniy_novgorod",
    "челябинск": "chelyabinsk",
    "самара": "samara",
    "уфа": "ufa",
    "ростов-на-дону": "rostov-na-donu",
    "краснодар": "krasnodar",
    "омск": "omsk",
    "воронеж": "voronezh",
    "пермь": "perm",
    "волгоград": "volgograd",
    "красноярск": "krasnoyarsk",
    "тюмень": "tyumen",
    "весь регион": "rossiya",
    "везде": "rossiya",
    "вся россия": "rossiya",
    "россия": "rossiya",
}

# Avito condition param values
CONDITION_PARAM: dict[str, str] = {
    "new": "1",       # новый
    "like_new": "2",  # хорошее
    "used": "3",      # среднее или ниже
    # "any" → не передаём параметр
}


class AvitoCollector(BaseCollector):
    """Collects listings from Avito.ru using Playwright."""

    BASE_URL = "https://www.avito.ru"

    def __init__(self, proxy_url: Optional[str] = None):
        super().__init__(proxy_url)
        self._browser = None
        self._context = None
        self._page = None

    # ── Browser lifecycle ─────────────────────────────────────────────────────

    async def _ensure_browser(self):
        if self._browser is not None:
            return
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        launch_kwargs = {"headless": settings.playwright_headless}
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
            extra_http_headers={"Accept-Language": "ru-RU,ru;q=0.9"},
        )
        self._page = await self._context.new_page()
        # Block images/fonts to speed up
        await self._page.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf}",
            lambda r: r.abort(),
        )
        log.info("Avito browser launched (headless=%s)", settings.playwright_headless)

    # ── Search ────────────────────────────────────────────────────────────────

    async def search(self, query: SearchQuery) -> list[RawListing]:
        await self._ensure_browser()
        url = self._make_search_url(query)
        log.info("[avito] GET %s", url)

        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await self._page.wait_for_timeout(settings.playwright_slow_mo)

            # Detect CAPTCHA / block
            if await self._page.query_selector("[class*='captcha'], [class*='blocked']"):
                log.warning("Avito: CAPTCHA detected, skipping")
                return []

            # Listing selectors (Avito changes HTML regularly — try multiple)
            items = await self._page.query_selector_all('[data-marker="item"]')
            if not items:
                items = await self._page.query_selector_all(
                    ".iva-item-root, .items-item, article[class*='item']"
                )

            log.info("[avito] Found %d raw items", len(items))

            results: list[RawListing] = []
            for item in items[:30]:
                try:
                    listing = await self._parse_item(item)
                    if listing and listing.price > 0:
                        results.append(listing)
                except Exception as e:
                    log.debug("Item parse error: %s", e)

            log.info("[avito] Parsed %d valid listings", len(results))
            return results

        except Exception as e:
            log.error("[avito] Search failed: %s", e)
            return []

    # ── Parsing ───────────────────────────────────────────────────────────────

    async def _parse_item(self, item) -> Optional[RawListing]:
        try:
            # URL + title
            link = await item.query_selector("a[data-marker='item-title'], a[href*='/']")
            if not link:
                return None

            href = await link.get_attribute("href") or ""
            url = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            if not url or "avito.ru" not in url:
                return None

            title = await self._extract_text(
                item,
                "[data-marker='item-title'] h3, "
                "[itemprop='name'], "
                "h3[class*='title'], "
                ".iva-item-title",
            )
            if not title:
                title = (await link.inner_text()).strip()[:200]
            if not title:
                return None

            # Price
            price = await self._extract_price(item)

            # Location
            location = await self._extract_text(
                item,
                "[data-marker='item-address'], "
                "[class*='geo-address'], "
                "[class*='location']",
            )

            # Seller
            seller = await self._extract_text(
                item,
                "[data-marker='seller-info/name'], "
                "[class*='seller-info'], "
                "[class*='seller']",
            )

            # Images count
            img_els = await item.query_selector_all("img[src*='avito']")
            images = [await el.get_attribute("src") or "" for el in img_els if el]

            # Published date
            published = await self._extract_text(
                item, "[data-marker='item-date'], [class*='date']"
            )

            return RawListing(
                source="avito",
                title=title.strip()[:500],
                price=price,
                location=(location or "").strip()[:200],
                url=url,
                seller_name=(seller or "").strip()[:200],
                images=[img for img in images if img][:10],
                published_at=published,
            )
        except Exception as e:
            log.debug("_parse_item error: %s", e)
            return None

    async def _extract_price(self, item) -> float:
        """Extract numeric price from listing card."""
        selectors = [
            "[data-marker='item-price'] meta[itemprop='price']",
            "[itemprop='price']",
            "[data-marker='item-price']",
            "[class*='price-text']",
            "[class*='price']",
        ]
        for sel in selectors:
            el = await item.query_selector(sel)
            if not el:
                continue
            # Try content attribute first (meta tag)
            content = await el.get_attribute("content")
            if content:
                try:
                    return float(re.sub(r"[^\d.]", "", content))
                except ValueError:
                    pass
            # Fall back to inner text
            text = (await el.inner_text()).strip()
            nums = re.sub(r"[^\d]", "", text)
            if nums:
                try:
                    return float(nums)
                except ValueError:
                    pass
        return 0.0

    @staticmethod
    async def _extract_text(parent, selector: str) -> Optional[str]:
        """Try each comma-separated selector, return first non-empty result."""
        for sel in selector.split(", "):
            el = await parent.query_selector(sel.strip())
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    return text
        return None

    # ── URL builder ───────────────────────────────────────────────────────────

    def _make_search_url(self, query: SearchQuery) -> str:
        """Build correct Avito search URL from SearchQuery."""
        # City slug
        city_slug = "rossiya"  # default: all Russia
        if query.location:
            slug = CITY_SLUGS.get(query.location.lower().strip())
            if slug:
                city_slug = slug
            else:
                # Use the city name directly as slug (some cities work as-is)
                city_slug = query.location.lower().strip().replace(" ", "_")

        # Search term
        search_term = query.query
        if query.keywords:
            # Add keywords not already in query
            extras = [k for k in query.keywords if k.lower() not in search_term.lower()]
            if extras:
                search_term = f"{search_term} {' '.join(extras[:3])}"

        # Query params
        params: dict = {"q": search_term}

        if query.max_price:
            params["pmax"] = int(query.max_price)
        if query.min_price:
            params["pmin"] = int(query.min_price)

        # Condition
        cond = getattr(query, "condition", "any") or "any"
        if cond in CONDITION_PARAM:
            params["q_type"] = CONDITION_PARAM[cond]

        url = f"{self.BASE_URL}/{city_slug}?{urlencode(params, quote_via=quote)}"
        return url

    # ── Cleanup ───────────────────────────────────────────────────────────────

    async def close(self):
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_pw") and self._pw:
            await self._pw.stop()
        log.info("Avito browser closed")
