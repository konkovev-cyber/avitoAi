"""Trust Scorer — оценка доверия к продавцу."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TrustScore:
    """Оценка доверия к продавцу (0-100)."""
    score: int = 0
    level: str = ""            # high | medium | low | suspicious
    factors: list[dict] = field(default_factory=list)
    explanation: str = ""


class SellerTrustScorer:
    """Оценка доверия к продавцу на основе данных."""

    def score(self, seller_data: dict) -> TrustScore:
        """
        Рассчитать доверие (0-100).

        seller_data keys:
            phone, website, inn, email,
            reviews_count, rating,
            account_age_days,
            has_photos, description_length,
            source_count, price_suspicious
        """
        score = 0
        factors = []

        # ── Positive factors ──────────────────────────────────────────────

        # Phone verified
        if seller_data.get("phone"):
            score += 12
            factors.append({"factor": "phone", "delta": +12, "reason": "Телефон есть"})

        # Website
        if seller_data.get("website"):
            score += 10
            factors.append({"factor": "website", "delta": +10, "reason": "Есть сайт"})

        # INN
        if seller_data.get("inn"):
            score += 15
            factors.append({"factor": "inn", "delta": +15, "reason": "Юрлицо (ИНН)"})

        # Email
        if seller_data.get("email"):
            score += 5
            factors.append({"factor": "email", "delta": +5, "reason": "Есть email"})

        # Reviews
        reviews = seller_data.get("reviews_count", 0)
        if reviews >= 100:
            score += 15
            factors.append({"factor": "reviews_100+", "delta": +15, "reason": f"{reviews} отзывов"})
        elif reviews >= 20:
            score += 10
            factors.append({"factor": "reviews_20+", "delta": +10, "reason": f"{reviews} отзывов"})
        elif reviews >= 5:
            score += 5
            factors.append({"factor": "reviews_5+", "delta": +5, "reason": f"{reviews} отзывов"})

        # Rating
        rating = seller_data.get("rating", 0)
        if rating >= 4.5:
            score += 10
            factors.append({"factor": "high_rating", "delta": +10, "reason": f"Рейтинг {rating}"})
        elif rating >= 4.0:
            score += 5
            factors.append({"factor": "good_rating", "delta": +5, "reason": f"Рейтинг {rating}"})

        # Account age
        age = seller_data.get("account_age_days", 0)
        if age >= 365:
            score += 8
            factors.append({"factor": "old_account", "delta": +8, "reason": f"Аккаунт {age} дней"})
        elif age >= 90:
            score += 4
            factors.append({"factor": "mid_account", "delta": +4, "reason": f"Аккаунт {age} дней"})

        # Multiple sources
        src_count = seller_data.get("source_count", 1)
        if src_count >= 3:
            score += 8
            factors.append({"factor": "multi_source", "delta": +8, "reason": f"На {src_count} площадках"})
        elif src_count >= 2:
            score += 4
            factors.append({"factor": "dual_source", "delta": +4, "reason": f"На {src_count} площадках"})

        # Photos
        if seller_data.get("has_photos"):
            score += 3
            factors.append({"factor": "photos", "delta": +3, "reason": "Есть фото"})

        # ── Negative factors ──────────────────────────────────────────────

        # No phone, no website, no inn
        if not seller_data.get("phone") and not seller_data.get("website") and not seller_data.get("inn"):
            score -= 15
            factors.append({"factor": "no_contacts", "delta": -15, "reason": "Нет контактов"})

        # New account
        if 0 < age < 30:
            score -= 10
            factors.append({"factor": "new_account", "delta": -10, "reason": f"Аккаунт {age} дней"})

        # No reviews at all
        if reviews == 0:
            score -= 5
            factors.append({"factor": "no_reviews", "delta": -5, "reason": "Нет отзывов"})

        # Suspiciously low price
        if seller_data.get("price_suspicious"):
            score -= 20
            factors.append({"factor": "suspicious_price", "delta": -20, "reason": "Подозрительно низкая цена"})

        # Short description
        desc_len = seller_data.get("description_length", 0)
        if 0 < desc_len < 20:
            score -= 5
            factors.append({"factor": "short_desc", "delta": -5, "reason": "Короткое описание"})

        # ── Final score ───────────────────────────────────────────────────

        final_score = max(0, min(100, score))

        if final_score >= 75:
            level = "high"
        elif final_score >= 50:
            level = "medium"
        elif final_score >= 25:
            level = "low"
        else:
            level = "suspicious"

        # Build explanation
        top_positive = sorted([f for f in factors if f["delta"] > 0], key=lambda x: -x["delta"])[:3]
        top_negative = sorted([f for f in factors if f["delta"] < 0], key=lambda x: x["delta"])[:2]

        parts = []
        for f in top_positive:
            parts.append(f"+{f['delta']} {f['reason']}")
        for f in top_negative:
            parts.append(f"{f['delta']} {f['reason']}")
        explanation = " | ".join(parts) if parts else "Мало данных"

        return TrustScore(
            score=final_score,
            level=level,
            factors=factors,
            explanation=explanation,
        )
