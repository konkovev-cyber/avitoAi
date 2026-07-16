"""
Milestone 2.3 — Tests: Yandex Market Connector (Commerce Intelligence).

Проверяет:
  1. Парсинг маркетплейса → Listing
  2. Evidence extraction (store_name, rating, reviews)
  3. Cross-source matching с Yandex Maps + Avito
  4. Positive: магазин + сайт компании
  5. False Merge: одинаковый бренд, разные продавцы
  6. Unknown: только название магазина
"""

from ..connectors.yandex_market import YandexMarketConnector
from ..models.listing import Listing
from ..resolution.matcher import EntityMatcher


# ── Test Data ─────────────────────────────────────────────────────────────

YMARKET_STORE_FULL = {
    "url": "https://market.yandex.ru/shop/holod-service",
    "title": "Холод-Сервис — запчасти для холодильников",
    "seller_name": "Холод-Сервис",
    "category": "Бытовая техника / Запчасти",
    "price": 2500,
    "rating": 4.8,
    "reviews_count": 156,
    "city": "Москва",
    "phone": "+7 (495) 111-22-33",
    "website": "holod-service.ru",
}

YMARKET_STORE_PHONE_ONLY = {
    "url": "https://market.yandex.ru/shop/teplo-mash",
    "title": "ТеплоМаш",
    "seller_name": "ТеплоМаш",
    "category": "Бытовая техника",
    "rating": 4.5,
    "reviews_count": 89,
    "city": "Москва",
    "phone": "+7 (495) 999-88-77",
}

YMARKET_STORE_NO_CONTACTS = {
    "url": "https://market.yandex.ru/shop/tech-store",
    "title": "Магазин техники",
    "seller_name": "Магазин техники",
    "category": "Бытовая техника",
    "rating": 4.2,
    "reviews_count": 34,
}

YMARKET_SAME_BRAND_DIFFERENT = {
    "url": "https://market.yandex.ru/shop/bosch-msk",
    "title": "Bosch-Сервис Москва",
    "seller_name": "Bosch-Сервис Москва",
    "category": "Бытовая техника / Bosch",
    "rating": 4.9,
    "reviews_count": 312,
    "city": "Москва",
}

YMARKET_SAME_BRAND_SPB = {
    "url": "https://market.yandex.ru/shop/bosch-spb",
    "title": "Bosch-Сервис СПб",
    "seller_name": "Bosch-Сервис СПб",
    "category": "Бытовая техника / Bosch",
    "rating": 4.7,
    "reviews_count": 98,
    "city": "Санкт-Петербург",
}

# Cross-source fixtures
YM_HOLOD_WITH_SITE = {
    "url": "https://market.yandex.ru/shop/holod-service",
    "title": "Холод-Сервис",
    "seller_name": "Холод-Сервис",
    "category": "Запчасти",
    "rating": 4.8,
    "reviews_count": 156,
    "city": "Москва",
    "phone": "+7 (495) 111-22-33",
}

SITE_HOLOD = {
    "url": "https://holod-service.ru",
    "title": "Холод-Сервис — ремонт и запчасти",
    "seller_name": "Холод-Сервис",
    "phone": "+7 (495) 111-22-33",
    "email": "info@holod-service.ru",
    "website": "holod-service.ru",
    "city": "Москва",
    "address": "ул. Промышленная, 5",
}


# ── Tests ─────────────────────────────────────────────────────────────────

def test_connector_contract():
    """Возвращает ConnectorResult с listings и evidence."""
    connector = YandexMarketConnector()
    result = connector.collect("холодильники", test_data=[YMARKET_STORE_FULL])
    assert len(result.listings) == 1
    assert len(result.evidence) >= 2
    assert result.listings[0].source == "yandex_market"


def test_normalize_with_all_fields():
    """normalize() сохраняет все поля магазина."""
    connector = YandexMarketConnector()
    listing = connector.normalize(YMARKET_STORE_FULL)
    assert listing.seller_name == "Холод-Сервис"
    assert listing.phone == "+7 (495) 111-22-33"
    assert listing.website == "holod-service.ru"
    assert listing.rating == 4.8
    assert listing.reviews_count == 156


def test_normalize_minimal():
    """normalize() работает с минимальными данными."""
    connector = YandexMarketConnector()
    listing = connector.normalize(YMARKET_STORE_NO_CONTACTS)
    assert listing.seller_name == "Магазин техники"
    assert listing.phone is None
    assert listing.rating == 4.2


def test_extract_evidence_store_name():
    """Извлекает name evidence из seller_name."""
    connector = YandexMarketConnector()
    listing = connector.normalize(YMARKET_STORE_FULL)
    evidence = connector.extract_evidence(listing)
    types = [e.type for e in evidence]
    assert "name_extracted" in types
    name_ev = [e for e in evidence if e.type == "name_extracted"][0]
    assert name_ev.value == "Холод-Сервис"
    assert name_ev.strength == 0.25


def test_extract_evidence_phone():
    """Извлекает phone evidence, если телефон указан."""
    connector = YandexMarketConnector()
    listing = connector.normalize(YMARKET_STORE_FULL)
    evidence = connector.extract_evidence(listing)
    types = [e.type for e in evidence]
    assert "phone_extracted" in types


def test_extract_evidence_no_contacts():
    """Из разреженных данных — только name evidence."""
    connector = YandexMarketConnector()
    listing = connector.normalize(YMARKET_STORE_NO_CONTACTS)
    evidence = connector.extract_evidence(listing)
    assert len(evidence) >= 1  # name как минимум
    assert all(e.type == "name_extracted" or "category" in e.type for e in evidence)


def test_connector_limitations():
    """Маркетплейс не даёт email, inn, address, working_hours."""
    connector = YandexMarketConnector()
    limits = connector.limitations()
    assert "email" in limits.never_available
    assert "inn" in limits.never_available
    assert "address" in limits.never_available
    assert "phone" in limits.sometimes_available


def test_cross_source_marketplace_to_website():
    """
    Positive Match: Яндекс Маркет + Сайт компании.

    Один телефон, одно имя → strong match.
    """
    matcher = EntityMatcher()

    market = Listing(
        id="ymk_cs1", category="Запчасти",
        source="yandex_market", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        rating=4.8, city="Москва",
    )
    site = Listing(
        id="site_cs1", category="Ремонт бытовой техники",
        source="company_website", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        website="holod-service.ru", email="info@holod-service.ru",
        city="Москва",
    )

    result = matcher.match(market, site)
    assert result.confidence > 0.50, f"Cross-source too low: {result.confidence}"
    assert result.decision in ("candidate", "strong", "verified")
    assert any(s["type"] == "phone" for s in result.signals), "Phone signal missing"


def test_cross_source_marketplace_to_yandex_maps():
    """
    Positive Match: Яндекс Маркет + Яндекс Карты.

    Один телефон, один город → strong match.
    """
    matcher = EntityMatcher()

    market = Listing(
        id="ymk_cs2", category="Бытовая техника",
        source="yandex_market", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        city="Москва",
    )
    ym = Listing(
        id="ym_cs2", category="Ремонт бытовой техники",
        source="yandex_maps", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        website="holod-service.ru", address="ул. Промышленная, 5",
        city="Москва",
    )

    result = matcher.match(market, ym)
    assert result.confidence > 0.50, f"Too low: {result.confidence}"
    assert result.decision in ("candidate", "strong", "verified")


def test_false_merge_same_brand_different_city():
    """
    False Merge: один бренд Bosch, разные города.

    Москва ≠ СПб → должны быть different.
    """
    matcher = EntityMatcher()

    msk = Listing(
        id="ymk_fm1", category="Бытовая техника / Bosch",
        source="yandex_market", url="", title="Bosch-Сервис Москва",
        seller_name="Bosch-Сервис Москва", city="Москва",
    )
    spb = Listing(
        id="ymk_fm2", category="Бытовая техника / Bosch",
        source="yandex_market", url="", title="Bosch-Сервис СПб",
        seller_name="Bosch-Сервис СПб", city="Санкт-Петербург",
    )

    result = matcher.match(msk, spb)
    assert result.confidence < 0.40, f"False merge risk: {result.confidence}"
    assert result.decision == "different"


def test_marketplace_unknown():
    """
    Unknown: только название магазина, нет контактов.

    Система не должна угадывать.
    """
    matcher = EntityMatcher()

    a = Listing(
        id="ymk_u1", category="Бытовая техника",
        source="yandex_market", url="", title="Магазин техники",
        seller_name="Магазин техники",
    )
    b = Listing(
        id="ymk_u2", category="Бытовая техника",
        source="yandex_market", url="", title="Магазин техники",
        seller_name="Магазин техники",
    )

    result = matcher.match(a, b)
    assert result.confidence < 0.40, f"Should be uncertain: {result.confidence}"
    assert result.decision == "different"


def test_triangulation_three_sources():
    """
    Триангуляция: Яндекс Маркет + Сайт + Яндекс Карты.

    Все три указывают на одного продавца → verified.
    """
    matcher = EntityMatcher()

    m1 = Listing(
        id="tri_market", category="Бытовая техника",
        source="yandex_market", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        city="Москва",
    )
    m2 = Listing(
        id="tri_site", category="Ремонт бытовой техники",
        source="company_website", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        website="holod-service.ru", city="Москва",
    )
    m3 = Listing(
        id="tri_maps", category="Ремонт бытовой техники",
        source="yandex_maps", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        address="ул. Промышленная, 5", city="Москва",
    )

    # Все пары должны быть strong
    pairs = [
        ("market↔site", matcher.match(m1, m2)),
        ("market↔maps", matcher.match(m1, m3)),
        ("site↔maps", matcher.match(m2, m3)),
    ]

    for name, result in pairs:
        assert result.confidence > 0.50, f"{name}: too low: {result.confidence}"
        assert result.decision in ("candidate", "strong", "verified"), f"{name}: {result.decision}"
        print(f"  ✅ {name}: {result.confidence:.2f} ({result.decision})")


def test_full_pipeline():
    """Полный прогон Yandex Market через Pipeline."""
    from ..pipeline import IntelligencePipeline

    pipe = IntelligencePipeline()
    connector = YandexMarketConnector()

    test_data = [
        YMARKET_STORE_FULL,
        YMARKET_STORE_PHONE_ONLY,
        YMARKET_STORE_NO_CONTACTS,
    ]

    result = pipe.run(connector, "запчасти", test_data=test_data)
    assert len(result.listings) == 3
    assert len(result.evidence) > 0
    assert len(result.profiles) == 3


if __name__ == "__main__":
    print("=== Milestone 2.3: Yandex Market Connector ===\n")

    tests = [
        test_connector_contract,
        test_normalize_with_all_fields,
        test_normalize_minimal,
        test_extract_evidence_store_name,
        test_extract_evidence_phone,
        test_extract_evidence_no_contacts,
        test_connector_limitations,
        test_cross_source_marketplace_to_website,
        test_cross_source_marketplace_to_yandex_maps,
        test_false_merge_same_brand_different_city,
        test_marketplace_unknown,
        test_triangulation_three_sources,
        test_full_pipeline,
    ]

    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")

    print(f"\n🎯 {passed}/{len(tests)} тестов пройдено")
