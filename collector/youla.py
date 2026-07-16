"""Youla (Юла) collector — GraphQL API (youla.ru by VK).

API: https://api.youla.ru/graphql
Формат: GraphQL POST запросы
Авторизация: не требуется для поиска
Города: slug из URL (например goryachiy_klyuch, moskva, sankt-peterburg)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional
from urllib.parse import quote

import httpx

from models import RawListing, SearchQuery
from .base import BaseCollector

log = logging.getLogger("market_agent.collector.youla")

YOULA_BASE = "https://youla.ru"
YOULA_API = "https://api.youla.ru/graphql"

# GraphQL запрос поиска объявлений
SEARCH_QUERY = """
query Search($query: String!, $priceMin: Int, $priceMax: Int, $citySlug: String, $first: Int) {
  search(
    text: $query
    priceMin: $priceMin
    priceMax: $priceMax
    city: $citySlug
    first: $first
  ) {
    edges {
      node {
        id
        slug
        title
        description
        price {
          amount
        }
        images {
          url
        }
        location {
          name
        }
        user {
          name
          rating
        }
        dateCreated
      }
    }
  }
}
"""

# Condition filter (Юла использует категориальный фильтр состояния)
CONDITION_PARAM: dict[str, Optional[int]] = {
    "new": 1,
    "like_new": 2,
    "used": 3,
    "any": None,
}


class YulaCollector(BaseCollector):
    """Collects listings from youla.ru via GraphQL API."""

    def __init__(self, proxy_url: Optional[str] = None):
        super().__init__(proxy_url)
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            kwargs: dict = {
                "headers": {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json",
                    "Accept-Language": "ru-RU,ru;q=0.9",
                    "Content-Type": "application/json",
                    "Origin": YOULA_BASE,
                    "Referer": YOULA_BASE + "/",
                },
                "timeout": httpx.Timeout(20.0),
                "follow_redirects": True,
            }
            if self.proxy_url:
                kwargs["proxies"] = {"all://": self.proxy_url}
            self._client = httpx.AsyncClient(**kwargs)
        return self._client

    async def search(self, query: SearchQuery) -> list[RawListing]:
        client = self._get_client()
        city_slug = self._city_slug(query.location)
        variables = {
            "query": query.query,
            "first": 30,
            "citySlug": city_slug,
        }
        if query.max_price:
            variables["priceMax"] = int(query.max_price)
        if query.min_price:
            variables["priceMin"] = int(query.min_price)

        log.info("[youla] Searching: %s in %s", query.query, city_slug or "all")
        try:
            resp = await client.post(
                YOULA_API,
                json={"query": SEARCH_QUERY, "variables": variables},
            )
            if resp.status_code != 200:
                log.warning("[youla] HTTP %s", resp.status_code)
                return await self._fallback_search(query)

            data = resp.json()
            edges = (
                data.get("data", {})
                    .get("search", {})
                    .get("edges", [])
            )
            log.info("[youla] Found %d items", len(edges))

            results = []
            for edge in edges:
                node = edge.get("node", {})
                listing = self._parse_node(node)
                if listing:
                    results.append(listing)
            return results

        except Exception as e:
            log.error("[youla] GraphQL error: %s", e)
            return await self._fallback_search(query)

    async def _fallback_search(self, query: SearchQuery) -> list[RawListing]:
        """Fallback: try REST-style search endpoint."""
        client = self._get_client()
        city_slug = self._city_slug(query.location)

        params: dict = {"q": query.query, "limit": "30"}
        if query.max_price:
            params["priceMax"] = str(int(query.max_price))
        if query.min_price:
            params["priceMin"] = str(int(query.min_price))
        if city_slug:
            params["city"] = city_slug

        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        url = f"https://api.youla.ru/api/v1/search?{qs}"

        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                log.warning("[youla] Fallback HTTP %s", resp.status_code)
                return []

            data = resp.json()
            items = data.get("data", data.get("items", data.get("results", [])))
            log.info("[youla] Fallback found %d items", len(items))
            results = []
            for item in items[:30]:
                listing = self._parse_item(item)
                if listing:
                    results.append(listing)
            return results
        except Exception as e:
            log.error("[youla] Fallback error: %s", e)
            return []

    def _parse_node(self, node: dict) -> Optional[RawListing]:
        """Parse GraphQL node."""
        try:
            node_id = str(node.get("id", ""))
            slug = node.get("slug", "")
            title = node.get("title", "")
            if not title:
                return None

            price_info = node.get("price", {}) or {}
            price = float(price_info.get("amount", 0) or 0)

            url = f"{YOULA_BASE}/product/{slug}" if slug else ""
            if not url:
                return None

            images = [
                img["url"] for img in (node.get("images") or [])
                if isinstance(img, dict) and img.get("url")
            ]

            location = (node.get("location") or {}).get("name", "")
            user = node.get("user") or {}
            seller_name = user.get("name", "")
            seller_rating = float(user.get("rating", 0) or 0) or None
            description = node.get("description", "") or ""

            return RawListing(
                source="youla",
                source_id=node_id,
                title=title[:500],
                description=description[:5000],
                price=price,
                location=location or None,
                url=url,
                images=images[:10],
                seller_name=seller_name or None,
                seller_rating=seller_rating,
            )
        except Exception as e:
            log.debug("_parse_node error: %s", e)
            return None

    def _parse_item(self, item: dict) -> Optional[RawListing]:
        """Parse REST API item."""
        try:
            title = item.get("title", "") or item.get("name", "")
            if not title:
                return None

            price_info = item.get("price", {}) or {}
            if isinstance(price_info, (int, float)):
                price = float(price_info)
            else:
                price = float(price_info.get("amount", 0) or 0)

            url = item.get("url", "") or item.get("link", "") or ""
            if url and not url.startswith("http"):
                url = f"{YOULA_BASE}{url}"
            if not url:
                return None

            seller = item.get("user", item.get("seller", {})) or {}
            seller_name = seller.get("name", "") if isinstance(seller, dict) else str(seller)
            seller_rating = float(seller.get("rating", 0) or 0) if isinstance(seller, dict) else None

            location = item.get("location", {}) or {}
            loc = location.get("name", "") if isinstance(location, dict) else str(location)

            images = []
            for img in item.get("images", item.get("photos", [])):
                if isinstance(img, str):
                    images.append(img)
                elif isinstance(img, dict):
                    images.append(img.get("url") or img.get("original") or "")
            images = [i for i in images if i]

            return RawListing(
                source="youla",
                source_id=str(item.get("id", "")),
                title=str(title)[:500],
                description=str(item.get("description", "") or "")[:5000],
                price=price,
                location=loc or None,
                url=url,
                images=images[:10],
                seller_name=seller_name or None,
                seller_rating=seller_rating,
            )
        except Exception as e:
            log.debug("_parse_item error: %s", e)
            return None

    @staticmethod
    def _city_slug(location: Optional[str]) -> Optional[str]:
        """Convert city name to Youla city slug."""
        if not location:
            return None
        CITY_MAP = {
            "москва": "moskva",
            "санкт-петербург": "sankt-peterburg",
            "спб": "sankt-peterburg",
            "питер": "sankt-peterburg",
            "екатеринбург": "ekaterinburg",
            "новосибирск": "novosibirsk",
            "казань": "kazan",
            "нижний новгород": "nizhniy_novgorod",
            "краснодар": "krasnodar",
            "ростов-на-дону": "rostov-na-donu",
            "омск": "omsk",
            "тюмень": "tyumen",
            "самара": "samara",
            "уфа": "ufa",
            "горячий ключ": "goryachiy_klyuch",
            "сочи": "sochi",
            "красноярск": "krasnoyarsk",
            "воронеж": "voronezh",
            "пермь": "perm",
            "волгоград": "volgograd",
            "челябинск": "chelyabinsk",
        }
        loc = location.lower().strip()
        if loc in CITY_MAP:
            return CITY_MAP[loc]
        # Try as-is (transliterated slug)
        slug = re.sub(r"[^a-z0-9_-]", "_", loc)
        return slug if slug else None

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
        log.info("Youla client closed")
