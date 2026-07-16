"""Base collector interface."""

from __future__ import annotations

import abc
import logging
from typing import Optional

from models import RawListing, SearchQuery

log = logging.getLogger("market_agent.collector")


class BaseCollector(abc.ABC):
    """Abstract base for all collectors."""

    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url
        self.name = self.__class__.__name__

    @abc.abstractmethod
    async def search(self, query: SearchQuery) -> list[RawListing]:
        """Search for listings matching the query.
        Returns list of new (previously unseen) listings.
        """
        ...

    async def close(self):
        """Cleanup resources."""
        pass

    def _make_search_url(self, query: SearchQuery) -> str:
        """Build a search URL from the query. Override per collector."""
        raise NotImplementedError

    def log(self, msg: str, level: str = "info"):
        getattr(log, level)("[%s] %s", self.name, msg)
