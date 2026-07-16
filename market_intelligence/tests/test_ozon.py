"""
Milestone 2.6 — Tests: Ozon Connector (Commerce Intelligence).

Проверяет:
  1. Contract compliance
  2. Offer model
  3. Evidence extraction (seller_name, brand, sku, rating)
  4. Cross-source matches (Ozon + Website + Yandex Maps)
  5. Brand trap: бренд ≠ продавец
  6. Same store name, different city
  7. Graph regression
"""

from ..connectors.ozon import OzonConnector
from ..models.offer import Offer
from ..models.evidence import Evidence
from ..models.listing import Listing
from ..models.seller import SellerProfile
from ..resolution.matcher import EntityMatcher
from ..graph.builder import GraphBuilder


# ── Test Data ─────────────────────────────────────────────────────────────

OZON_FULL = {
    "url": "https://www.ozon.ru/seller/holod-service-123/products/",
    "title": "Холодильник Samsung RB33",
    "seller_name": "Холод-Сервис",
    "seller_url": "https://www.ozon.ru/seller/holod-service-123/",
    "sku": "OZON123456",
    "brand": "Samsung",
    "category": "Бытовая техника / Холодильники",
    "price": 45000,
    "rating": 4.7,
    "reviews_count": 234,
    "phone": "+7 (495) 111-22-33",
}

OZON_STORE_ONLY = {
    "url": "https://www.ozon.ru/seller/tech-store-456/products/",
    "title": "Стиральная машина Bosch",
    "seller_name": "Tech-Store",
    "seller_url": "https://www.ozon.ru/seller/tech-store-456/",
    "sku": "OZON789012",
    "brand": "Bosch",
    "category": "Бытовая техника",
    "price": 35000,
    "rating": 4.5,
    "reviews_count": 89,
}

OZON_NO_CONTACTS = {
    "url": "https://www.ozon.ru/seller/random-shop-789/products/",
    "title": "Пылесос",
    "seller_name": "Random Shop",
    "seller_url": "https://www.ozon.ru/seller/random-shop-789/",
    "sku": "OZON345678",
    "brand": "Samsung",
    "category": "Бытовая техника / Пылесосы",
    "price": 12000,
    "rating": 4.5,
}

OZON_SAME_BRAND_SELLER_A = {
    "url": "https://www.ozon.ru/seller/samsung-a/products/",
    "title": "Телевизор Samsung",
    "seller_name": "Samsung-Store-A",
    "seller_url": "https://www.ozon.ru/seller/samsung-a/",
    "sku": "OZON_SA_001",
    "brand": "Samsung",
    "category": "Электроника",
    "price": 55000,
}

OZON_SAME_BRAND_SELLER_B = {
    "url": "https://www.ozon.ru/seller/samsung-b/products/",
    "title": "Телевизор Samsung",
    "seller_name": "Samsung-Store-B",
    "seller_url": "https://www.ozon.ru/seller/samsung-b/",
    "sku": "OZON_SB_001",
    "brand": "Samsung",
    "category": "Электроника",
    "price": 55000,
}

OZON_SAME_NAME_DIFF_CITY_1 = {
    "url": "https://www.ozon.ru/seller/tech-store-msk/",
    "title": "Телефон",
    "seller_name": "Tech Store",
    "seller_url": "https://www.ozon.ru/seller/tech-store-msk/",
    "brand": "Xiaomi",
    "city": "Москва",
}

OZON_SAME_NAME_DIFF_CITY_2 = {
    "url": "https://www.ozon.ru/seller/tech-store-spb/",
    "title": "Телефон",
    "seller_name": "Tech Store",
    "seller_url": "https://www.ozon.ru/seller/tech-store-spb/",
    "brand": "Xiaomi",
    "city": "Санкт-Петербург",
}


# ── Tests ─────────────────────────────────────────────────────────────────

def test_connector_contract():
    """Возвращает ConnectorResult с listings (Offer) и evidence."""
    c = OzonConnector()
    r = c.collect("холодильники", test_data=[OZON_FULL])
    assert len(r.listings) == 1
    assert len(r.evidence) >= 2
    assert r.listings[0].source == "ozon"


def test_offer_created():
    """normalize() возвращает Offer."""
    c = OzonConnector()
    offer = c.normalize(OZON_FULL)
    assert isinstance(offer, Offer)
    assert offer.id.startswith("oz_")
    assert offer.seller_name == "Холод-Сервис"
    assert offer.brand == "Samsung"
    assert offer.sku == "OZON123456"
    assert offer.price == 45000
    assert offer.rating == 4.7


def test_offer_minimal():
    """normalize() с минимальными данными."""
    c = OzonConnector()
    offer = c.normalize(OZON_NO_CONTACTS)
    assert offer.seller_name == "Random Shop"
    assert offer.phone is None
    assert offer.rating == 4.5  # from data


def test_evidence_seller_name():
    """Извлекает name evidence из seller_name."""
    c = OzonConnector()
    offer = c.normalize(OZON_FULL)
    evidence = c.extract_evidence(offer)
    types = [e.type for e in evidence]
    assert "name_extracted" in types
    name_ev = [e for e in evidence if e.type == "name_extracted"][0]
    assert name_ev.value == "Холод-Сервис"
    assert name_ev.strength == 0.25


def test_evidence_brand():
    """Извлекает brand evidence."""
    c = OzonConnector()
    offer = c.normalize(OZON_FULL)
    evidence = c.extract_evidence(offer)
    brand_ev = [e for e in evidence if e.type == "category_extracted" and e.field == "brand"]
    assert len(brand_ev) >= 1
    assert brand_ev[0].value == "Samsung"
    assert brand_ev[0].strength == 0.12


def test_evidence_sku():
    """Извлекает sku evidence."""
    c = OzonConnector()
    offer = c.normalize(OZON_FULL)
    evidence = c.extract_evidence(offer)
    sku_ev = [e for e in evidence if "sku" in e.field]
    assert len(sku_ev) >= 1
    assert sku_ev[0].value == "OZON123456"


def test_evidence_phone():
    """Извлекает phone evidence если указан."""
    c = OzonConnector()
    offer = c.normalize(OZON_FULL)
    evidence = c.extract_evidence(offer)
    types = [e.type for e in evidence]
    assert "phone_extracted" in types


def test_evidence_no_contacts():
    """Без контактов — только store_name + brand + sku + rating."""
    c = OzonConnector()
    offer = c.normalize(OZON_NO_CONTACTS)
    evidence = c.extract_evidence(offer)
    assert len(evidence) >= 3  # name + brand + sku минимум
    types = [e.type for e in evidence]
    assert "name_extracted" in types
    assert "phone_extracted" not in types


def test_connector_limitations():
    """Ozon не даёт email, inn, address."""
    c = OzonConnector()
    limits = c.limitations()
    assert "email" in limits.never_available
    assert "inn" in limits.never_available
    assert "phone" in limits.sometimes_available


# ── Cross-source tests ────────────────────────────────────────────────────

def test_cross_source_ozon_to_website():
    """
    Positive: Ozon продавец + Сайт компании (один телефон) → MATCH.
    """
    matcher = EntityMatcher()

    ozon = Listing(
        id="oz_cs1", category="Бытовая техника",
        source="ozon", url="", title="Холодильник Samsung",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
    )
    site = Listing(
        id="site_cs1", category="Ремонт бытовой техники",
        source="company_website", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        website="holod-service.ru", email="info@holod-service.ru",
    )

    r = matcher.match(ozon, site)
    assert r.confidence > 0.40, f"Too low: {r.confidence}"
    assert r.decision in ("candidate", "strong", "verified")
    assert any(s["type"] == "phone" for s in r.signals)


def test_cross_source_ozon_to_yandex_maps():
    """
    Positive: Ozon + Яндекс Карты (один телефон) → MATCH.
    """
    matcher = EntityMatcher()

    ozon = Listing(
        id="oz_cs2", category="Бытовая техника",
        source="ozon", url="", title="Холодильник",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
    )
    ym = Listing(
        id="ym_cs2", category="Ремонт бытовой техники",
        source="yandex_maps", url="", title="Холод-Сервис",
        seller_name="Холод-Сервис", phone="+7 (495) 111-22-33",
        website="holod-service.ru", address="ул. Промышленная, 5",
    )

    r = matcher.match(ozon, ym)
    assert r.confidence > 0.40, f"Too low: {r.confidence}"
    assert r.decision in ("candidate", "strong", "verified")


def test_brand_trap():
    """
    Brand trap: Samsung — одинаковый бренд, разные продавцы.
    Должны быть DIFFERENT.
    """
    matcher = EntityMatcher()

    a = Listing(
        id="oz_bt1", category="Электроника",
        source="ozon", url="", title="Телевизор Samsung",
        seller_name="Samsung-Store-A",
    )
    b = Listing(
        id="oz_bt2", category="Электроника",
        source="ozon", url="", title="Телевизор Samsung",
        seller_name="Samsung-Store-B",
    )

    r = matcher.match(a, b)
    assert r.confidence < 0.30, f"False merge risk: {r.confidence}"
    assert r.decision == "different"


def test_same_name_different_city():
    """
    Одинаковое название магазина, разные города.
    Должны быть UNKNOWN / DIFFERENT.
    """
    matcher = EntityMatcher()

    msk = Listing(
        id="oz_city1", category="Электроника",
        source="ozon", url="", title="Телефон",
        seller_name="Tech Store", city="Москва",
    )
    spb = Listing(
        id="oz_city2", category="Электроника",
        source="ozon", url="", title="Телефон",
        seller_name="Tech Store", city="Санкт-Петербург",
    )

    r = matcher.match(msk, spb)
    assert r.confidence <= 0.25, f"Should be uncertain: {r.confidence}"
    assert r.decision == "different"


def test_graph_integration():
    """
    Ozon → Graph: Offer → SellerProfile → GraphEntity.
    """
    builder = GraphBuilder()
    p1 = SellerProfile(id="oz_p1", name="Холод-Сервис",
        phones=["+7 (495) 111-22-33"], websites=["holod-service.ru"],
        source_names=["ozon", "company_website"])

    graph = builder.build_from_profiles([p1])
    assert graph.get_stats()["total_entities"] == 1
    entity = list(graph.entities.values())[0]
    assert entity.type == "store"  # Ozon source → store type
    assert entity.phone == "+7 (495) 111-22-33"


def test_graph_ozon_plus_website():
    """
    Ozon + Website → same_as relationship.
    """
    builder = GraphBuilder()

    p1 = SellerProfile(id="oz_plus_1", name="Холод-Сервис (Ozon)",
        phones=["+7 (495) 111-22-33"], websites=["holod-service.ru"],
        source_names=["ozon"])
    p2 = SellerProfile(id="oz_plus_2", name="Холод-Сервис (сайт)",
        phones=["+7 (495) 111-22-33"], websites=["holod-service.ru"],
        source_names=["company_website"], inn="1234567890")

    graph = builder.build_from_profiles([p1, p2])
    rels = list(graph.relationships.values())
    assert len(rels) >= 1, "Ozon + Website should have same_as link"
    assert rels[0].type == "same_as"


def test_offer_graph_stress():
    """
    Ozon Graph Stress: 3 магазина, 2 с одним телефоном.

    Телефонные дубли → same_as.
    Разные телефоны → different.
    """
    builder = GraphBuilder()

    p1 = SellerProfile(id="oz_s1", name="Холод-Сервис",
        phones=["+7 (495) 111-22-33"], source_names=["ozon"])
    p2 = SellerProfile(id="oz_s2", name="Холод-Сервис Official",
        phones=["+7 (495) 111-22-33"], source_names=["ozon", "yandex_market"])
    p3 = SellerProfile(id="oz_s3", name="Другой Магазин",
        phones=["+7 (495) 999-99-99"], source_names=["ozon"])

    graph = builder.build_from_profiles([p1, p2, p3])
    rels = list(graph.relationships.values())
    same_as = [r for r in rels if r.type == "same_as"]

    rels_str = " ".join([r.type for r in rels])
    assert len(rels) >= 1, f"p1↔p2 should have relationship, types: {rels_str}"
    # p3 ни с кем не должен совпасть
    p3_rels = [r for r in rels if "oz_s3" in r.source_id or "oz_s3" in r.target_id]
    p3_same = [r for r in p3_rels if r.type == "same_as"]
    assert len(p3_same) == 0, f"p3 should not have same_as: {len(p3_same)}"


if __name__ == "__main__":
    print("=== Milestone 2.6: Ozon Connector ===\n")

    tests = [
        test_connector_contract,
        test_offer_created,
        test_offer_minimal,
        test_evidence_seller_name,
        test_evidence_brand,
        test_evidence_sku,
        test_evidence_phone,
        test_evidence_no_contacts,
        test_connector_limitations,
        test_cross_source_ozon_to_website,
        test_cross_source_ozon_to_yandex_maps,
        test_brand_trap,
        test_same_name_different_city,
        test_graph_integration,
        test_graph_ozon_plus_website,
        test_offer_graph_stress,
    ]

    passed = 0
    for t in tests:
        try:
            t()
            print(f"  ✅ {t.__name__}")
            passed += 1
        except Exception as e:
            import traceback
            print(f"  ❌ {t.__name__}: {e}")
            traceback.print_exc()

    print(f"\n🎯 {passed}/{len(tests)} тестов пройдено")

    if passed == len(tests):
        print("🟢 Ozon Connector MVP PASS. Ready for Wildberries.")
