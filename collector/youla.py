"""Yula collector — requests-based using internal API."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional
from urllib.parse import quote

import httpx

from config import settings
from models import RawListing, SearchQuery
from .base import BaseCollector

log = logging.getLogger("market_agent.collector.youla")


class YulaCollector(BaseCollector):
    """Collects listings from Yula.io using their internal API."""

    BASE_URL = "https://youla.ru"
    API_URL = "https://api.youla.ru/graphql"

    def __init__(self, proxy_url: Optional[str] = None):
        super().__init__(proxy_url)
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        if self._client is not None:
            return
        kwargs = {
            "headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "ru-RU,ru;q=0.9",
            },
            "timeout": httpx.Timeout(15.0),
        }
        if self.proxy_url:
            kwargs["proxies"] = self.proxy_url
        self._client = httpx.AsyncClient(**kwargs)

    async def search(self, query: SearchQuery) -> list[RawListing]:
        await self._ensure_client()
        url = self._make_search_url(query)
        self.log(f"Searching: {url}")

        try:
            resp = await self._client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                self.log(f"HTTP {resp.status_code}", "warning")
                return []

            data = resp.json()
            items = self._extract_items(data)
            self.log(f"Found {len(items)} items")

            results = []
            for item in items[:30]:
                try:
                    listing = self._parse_item(item)
                    if listing:
                        results.append(listing)
                except Exception as e:
                    self.log(f"Parse error: {e}", "warning")

            return results

        except Exception as e:
            self.log(f"Search error: {e}", "error")
            return []

    def _extract_items(self, data: dict) -> list[dict]:
        """Extract listing items from Yula API response."""
        # Try different response structures
        products = data.get("data", {}).get("products", [])
        if products:
            return products
        results = data.get("results", [])
        if results:
            return results
        items = data.get("items", [])
        if items:
            return items
        # Maybe wrapped in searchResults
        search = data.get("data", {}).get("searchResults", {})
        items = search.get("products", search.get("items", []))
        return items

    def _parse_item(self, item: dict) -> Optional[RawListing]:
        try:
            title = item.get("title", "") or item.get("name", "")
            price_info = item.get("price", {}) or {}
            if isinstance(price_info, (int, float)):
                price = float(price_info)
            else:
                price = float(price_info.get("amount", 0))

            url = item.get("url", "") or item.get("link", "") or ""
            if url and not url.startswith("http"):
                url = f"{self.BASE_URL}{url}"

            seller = item.get("seller", {}) or {}
            if isinstance(seller, str):
                seller_name = seller
            else:
                seller_name = seller.get("name", "") or item.get("author", "")

            location = item.get("location", {}) or {}
            if isinstance(location, str):
                loc = location
            else:
                loc = location.get("name", "") or item.get("city", "")

            images = []
            for img in item.get("images", item.get("photos", [])):
                if isinstance(img, str):
                    images.append(img)
                elif isinstance(img, dict):
                    images.append(img.get("url", img.get("original", "")))

            return RawListing(
                source="youla",
                source_id=str(item.get("id", "")),
                title=str(title)[:500],
                description=str(item.get("description", "") or "")[:5000],
                price=price,
                location=loc or None,
                url=url,
                images=images[:5],
                seller_name=str(seller_name) or None,
            )
        except Exception as e:
            self.log(f"Item parse error: {e}", "warning")
            return None

    def _make_search_url(self, query: SearchQuery) -> str:
        params = {"q": query.query}
        if query.max_price:
            params["priceMax"] = str(int(query.max_price))
        if query.min_price:
            params["priceMin"] = str(int(query.min_price))
        if query.location:
            params["city"] = query.location
        qs = "&".join(f"{k}={quote(v)}" for k, v in params.items())
        return f"{self.BASE_URL}/api/search?{qs}"

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
        self.log("Closed")
