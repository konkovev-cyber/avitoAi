"""Entity Resolution Matcher — находит и объединяет профили продавцов."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

from ..models.listing import Listing
from ..models.evidence import Evidence
from ..models.seller import SellerProfile, MatchHypothesis

# Веса сигналов из SIGNAL_REGISTRY.md v2
SIGNAL_WEIGHTS = {
    "inn": 0.40,
    "phone": 0.35,
    "website": 0.35,
    "address": 0.30,
    "email": 0.25,
    "name": 0.08,
    "city": 0.08,
}

# Уровни confidence
THRESHOLD_AUTO_MERGE = 0.85
THRESHOLD_SUGGEST = 0.65
THRESHOLD_REVIEW = 0.40


@dataclass
class MatchResult:
    """Результат сравнения двух Listing."""
    confidence: float = 0.0
    signals: list[dict] = field(default_factory=list)
    negative_signals: list[dict] = field(default_factory=list)
    decision: str = "unknown"       # different | candidate | strong | verified
    explanation: str = ""
    requires_review: bool = True


class EntityMatcher:
    """Сравнивает Listing и определяет, принадлежат ли они одному продавцу."""

    def match(self, a: Listing, b: Listing) -> MatchResult:
        """Сравнить два Listing, вернуть MatchResult."""
        result = MatchResult()
        signals = []
        negative = []

        # 1. Телефон (самый сильный сигнал)
        if a.phone and b.phone:
            if self._same_phone(a.phone, b.phone):
                signals.append({
                    "type": "phone",
                    "weight": SIGNAL_WEIGHTS["phone"],
                    "value_a": a.phone,
                    "value_b": b.phone,
                })

        # 2. Сайт
        if a.website and b.website:
            if self._same_website(a.website, b.website):
                signals.append({
                    "type": "website",
                    "weight": SIGNAL_WEIGHTS["website"],
                    "value_a": a.website,
                    "value_b": b.website,
                })

        # 3. Адрес
        if a.address and b.address:
            if self._same_address(a.address, b.address):
                signals.append({
                    "type": "address",
                    "weight": SIGNAL_WEIGHTS["address"],
                    "value_a": a.address,
                    "value_b": b.address,
                })
            else:
                negative.append({
                    "type": "address_conflict",
                    "weight": -0.15,
                    "value_a": a.address,
                    "value_b": b.address,
                })

        # 4. Email
        if a.email and b.email:
            if self._same_email(a.email, b.email):
                signals.append({
                    "type": "email",
                    "weight": SIGNAL_WEIGHTS["email"],
                    "value_a": a.email,
                    "value_b": b.email,
                })

        # 5. Название (слабый сигнал)
        if a.seller_name and b.seller_name:
            similarity = self._name_similarity(a.seller_name, b.seller_name)
            if similarity > 0.7:
                weight = SIGNAL_WEIGHTS["name"] * similarity
                signals.append({
                    "type": "name",
                    "weight": round(weight, 3),
                    "value_a": a.seller_name,
                    "value_b": b.seller_name,
                    "similarity": round(similarity, 2),
                })
            elif similarity < 0.3 and len(signals) > 0:
                # Разные названия при прочих совпадениях — допустимо
                pass

        # 6. Город (слабый сигнал)
        if a.city and b.city and a.city.lower() == b.city.lower():
            signals.append({
                "type": "city",
                "weight": SIGNAL_WEIGHTS["city"],
                "value_a": a.city,
                "value_b": b.city,
            })
        elif a.city and b.city and a.city.lower() != b.city.lower():
            negative.append({
                "type": "city_conflict",
                "weight": -0.20,
                "value_a": a.city,
                "value_b": b.city,
            })

        # Подсчёт confidence
        total = sum(s["weight"] for s in signals)
        neg_total = sum(n["weight"] for n in negative)
        confidence = max(0.0, min(1.0, total + neg_total))

        result.signals = signals
        result.negative_signals = negative
        result.confidence = round(confidence, 3)
        result.decision = self._classify(confidence, signals, negative)
        result.explanation = self._build_explanation(result)
        result.requires_review = result.decision in ("candidate",)

        return result

    def build_profile(self, listings: list[Listing], name: str) -> SellerProfile:
        """Построить SellerProfile из списка Listing."""
        profile = SellerProfile(
            id=f"seller_{hashlib.md5(name.encode()).hexdigest()[:8]}",
            name=name,
        )

        for l in listings:
            profile.listing_ids.append(l.id)
            profile.source_names.append(l.source)
            if l.phone and l.phone not in profile.phones:
                profile.phones.append(l.phone)
            if l.email and l.email not in profile.emails:
                profile.emails.append(l.email)
            if l.website and l.website not in profile.websites:
                profile.websites.append(l.website)
            if l.address and l.address not in profile.addresses:
                profile.addresses.append(l.address)

        profile.evidence_density = (
            len(profile.phones)
            + len(profile.emails)
            + len(profile.websites)
            + len(profile.addresses)
            + (1 if profile.inn else 0)
        )

        return profile

    def compare_profiles(self, a: SellerProfile, b: SellerProfile) -> MatchResult:
        """Сравнить два профиля продавцов."""
        # Создаём временные Listing для сравнения по сигналам
        listing_a = Listing(
            id="compare_a",
            source="profile",
            url="",
            title=a.name,
            category="Ремонт бытовой техники",
            seller_name=a.name,
            phone=a.phones[0] if a.phones else None,
            email=a.emails[0] if a.emails else None,
            website=a.websites[0] if a.websites else None,
            address=a.addresses[0] if a.addresses else None,
        )
        listing_b = Listing(
            id="compare_b",
            source="profile",
            url="",
            title=b.name,
            category="Ремонт бытовой техники",
            seller_name=b.name,
            phone=b.phones[0] if b.phones else None,
            email=b.emails[0] if b.emails else None,
            website=b.websites[0] if b.websites else None,
            address=b.addresses[0] if b.addresses else None,
        )
        return self.match(listing_a, listing_b)

    # ── Signal matchers ───────────────────────────────────────────────────

    @staticmethod
    def _same_phone(a: str, b: str) -> bool:
        """Сравнить телефоны (нормализованные)."""
        a_digits = "".join(c for c in a if c.isdigit())
        b_digits = "".join(c for c in b if c.isdigit())
        if not a_digits or not b_digits:
            return False
        return a_digits[-10:] == b_digits[-10:]  # последние 10 цифр

    @staticmethod
    def _same_website(a: str, b: str) -> bool:
        """Сравнить домены сайтов."""
        a_clean = a.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        b_clean = b.lower().replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
        return a_clean == b_clean

    @staticmethod
    def _same_address(a: str, b: str) -> bool:
        """Сравнить адреса (нормализованные, частичное совпадение)."""
        def norm(addr: str) -> str:
            a = addr.lower()
            a = a.replace("ул.", "").replace("улица", "")
            a = a.replace("д.", "").replace("дом", "").replace("домовладение", "")
            a = a.replace(" ", "").replace(",", "").replace(".", "").strip()
            # Удалить название города/региона для частичного сравнения
            a = a.replace("москва", "").replace("спб", "").replace("санктпетербург", "")
            for city in ["жуковский", "лыткарино", "домодедово", "щелково"]:
                a = a.replace(city, "")
            return a
        na = norm(a)
        nb = norm(b)
        return na == nb or na.startswith(nb) or nb.startswith(na)

    @staticmethod
    def _same_email(a: str, b: str) -> bool:
        return a.lower().strip() == b.lower().strip()

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        """Простая оценка схожести названий."""
        a_low = a.lower().strip()
        b_low = b.lower().strip()
        if a_low == b_low:
            return 1.0
        # Одно содержит другое
        if a_low in b_low or b_low in a_low:
            return 0.8
        # Общие слова
        a_words = set(a_low.split())
        b_words = set(b_low.split())
        if a_words and b_words:
            intersection = a_words & b_words
            return len(intersection) / max(len(a_words), len(b_words))
        return 0.0

    # ── Classification ────────────────────────────────────────────────────

    @staticmethod
    def _classify(confidence: float, signals: list, negative: list) -> str:
        """Определить решение на основе confidence и сигналов."""
        if confidence >= THRESHOLD_AUTO_MERGE and len(signals) >= 2:
            if not any(n["weight"] < -0.3 for n in negative):
                return "verified"
            return "strong"
        if confidence >= THRESHOLD_SUGGEST:
            return "candidate"
        if confidence >= THRESHOLD_REVIEW:
            return "candidate"
        return "different"

    @staticmethod
    def _build_explanation(result: MatchResult) -> str:
        parts = []
        for s in result.signals:
            parts.append(f"✓ {s['type']} (вес {s['weight']})")
        for n in result.negative_signals:
            parts.append(f"✗ {n['type']} (вес {n['weight']})")
        if not parts:
            parts.append("Нет совпадающих сигналов")
        parts.append(f"→ Итого: {result.confidence:.2f} = {result.decision}")
        return "\n".join(parts)
