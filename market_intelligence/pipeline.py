"""Pipeline — оркестратор: Connector → Listing → Evidence → Seller Profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .connectors.base import BaseConnector, ConnectorResult
from .models.listing import Listing
from .models.evidence import Evidence
from .models.seller import SellerProfile
from .resolution.matcher import EntityMatcher, MatchResult


@dataclass
class PipelineResult:
    """Результат работы пайплайна."""
    listings: list[Listing] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    profiles: list[SellerProfile] = field(default_factory=list)
    match_results: list[MatchResult] = field(default_factory=list)


class IntelligencePipeline:
    """Главный пайплайн: Connector → Listing → Evidence → Seller."""

    def __init__(self):
        self.matcher = EntityMatcher()

    def run_connector(self, connector: BaseConnector, query: str, **kwargs) -> ConnectorResult:
        """Запустить коннектор, получить Listing + Evidence."""
        result = connector.collect(query, **kwargs)
        return result

    def build_profiles(self, listings: list[Listing]) -> list[SellerProfile]:
        """Построить профили продавцов из списка Listing."""
        if not listings:
            return []

        # Для MVP: каждый Listing — отдельный профиль
        # (полноценная ER будет в следующей итерации)
        profiles = []
        seen = set()

        for l in listings:
            # Пропускаем дубли по URL
            if l.url in seen:
                continue
            seen.add(l.url)

            profile = self.matcher.build_profile([l], l.seller_name or l.title)
            profile.confidence = 0.50
            profile.status = "hypothesis"
            profiles.append(profile)

        return profiles

    def compare_all(self, profiles: list[SellerProfile]) -> list[MatchResult]:
        """Попарно сравнить все профили."""
        results = []
        for i in range(len(profiles)):
            for j in range(i + 1, len(profiles)):
                result = self.matcher.compare_profiles(profiles[i], profiles[j])
                results.append(result)
        return results

    def run(self, connector: BaseConnector, query: str, **kwargs) -> PipelineResult:
        """Полный прогон: коннектор → профили → сравнение."""
        result = PipelineResult()

        # 1. Connector → Listing + Evidence
        connector_result = self.run_connector(connector, query, **kwargs)
        if not connector_result.listings:
            return result

        result.listings = connector_result.listings
        result.evidence = connector_result.evidence

        # 2. Построить профили
        result.profiles = self.build_profiles(connector_result.listings)

        # 3. Сравнить профили (если их ≥ 2)
        if len(result.profiles) >= 2:
            result.match_results = self.compare_all(result.profiles)

        return result
