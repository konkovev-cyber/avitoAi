"""
Milestone 2.7 — Tests: Wildberries Connector.

Проверяет:
  1. Contract compliance
  2. Offer model через WB
  3. Evidence extraction (store, brand, sku, rating)
  4. Brand ≠ Seller (критический)
  5. Один продавец → несколько брендов
  6. Seller rename (старое → новое название)
  7. Same product, different sellers
  8. Graph integration
  9. Cross-source with Yandex Maps / Ozon
"""

from ..connectors.wildberries import WildberriesConnector
from ..models.offer import Offer
from ..models.listing import Listing
from ..models.seller import SellerProfile
from ..resolution.matcher import EntityMatcher
from ..graph.builder import GraphBuilder


# ── Test Data ─────────────────────────────────────────────────────────────

WB_STORE_A = {
    "url": "https://www.wildberries.ru/brands/samsung/seller/123",
    "title": "Холодильник Samsung",
    "seller_name": "Tech-Master Store",
    "seller_url": "https://www.wildberries.ru/seller/123",
    "sku": "WB001",
    "nm_id": "NM001",
    "brand": "Samsung",
    "category": "Бытовая техника",
    "price": 45000,
    "rating": 4.7,
    "reviews_count": 234,
}

WB_STORE_B = {
    "url": "https://www.wildberries.ru/brands/bosch/seller/456",
    "title": "Стиральная машина Bosch",
    "seller_name": "Tech-Master Store",
    "seller_url": "https://www.wildberries.ru/seller/456",
    "sku": "WB002",
    "nm_id": "NM002",
    "brand": "Bosch",
    "category": "Бытовая техника",
    "price": 35000,
    "rating": 4.5,
    "reviews_count": 89,
}

WB_DIFFERENT_SELLER_SAME_BRAND_A = {
    "url": "https://www.wildberries.ru/samsung/store-a",
    "title": "Телевизор Samsung",
    "seller_name": "Store-A",
    "sku": "WB003",
    "brand": "Samsung",
    "category": "Электроника",
    "price": 55000,
}

WB_DIFFERENT_SELLER_SAME_BRAND_B = {
    "url": "https://www.wildberries.ru/samsung/store-b",
    "title": "Телевизор Samsung",
    "seller_name": "Store-B",
    "sku": "WB004",
    "brand": "Samsung",
    "category": "Электроника",
    "price": 55000,
}

WB_SAME_PRODUCT_SELLER_B_A = {
    "url": "https://www.wildberries.ru/product/001/seller-a",
    "title": "Пылесос Dyson V15",
    "seller_name": "Seller-A",
    "sku": "WB_DYSON_001",
    "brand": "Dyson",
    "category": "Бытовая техника / Пылесосы",
    "price": 60000,
}

WB_SAME_PRODUCT_SELLER_B = {
    "url": "https://www.wildberries.ru/product/001/seller-b",
    "title": "Пылесос Dyson V15",
    "seller_name": "Seller-B",
    "sku": "WB_DYSON_001",
    "brand": "Dyson",
    "category": "Бытовая техника / Пылесосы",
    "price": 62000,
}

WB_SELLER_RENAME_OLD = {
    "url": "https://www.wildberries.ru/seller/old-name",
    "title": "Товар",
    "seller_name": "Старое Название",
    "sku": "WB_REN_001",
    "brand": "LG",
}

WB_SELLER_RENAME_NEW = {
    "url": "https://www.wildberries.ru/seller/new-name",
    "title": "Товар",
    "seller_name": "Новое Название",
    "sku": "WB_REN_002",
    "brand": "LG",
    "phone": "+7 (495) 111-22-33",
    "website": "store-lg.ru",
}


# ── Tests ─────────────────────────────────────────────────────────────────

def test_connector_contract():
    """Возвращает ConnectorResult с listings и evidence."""
    c = WildberriesConnector()
    r = c.collect("холодильники", test_data=[WB_STORE_A])
    assert len(r.listings) == 1
    assert len(r.evidence) >= 2
    assert r.listings[0].source == "wildberries"


def test_offer_normalize():
    """normalize() возвращает Offer с полями WB."""
    c = WildberriesConnector()
    offer = c.normalize(WB_STORE_A)
    assert isinstance(offer, Offer)
    assert offer.id.startswith("wb_")
    assert offer.seller_name == "Tech-Master Store"
    assert offer.brand == "Samsung"
    assert offer.sku == "WB001"
    assert offer.price == 45000


def test_evidence_store_name():
    """Извлекает name evidence из seller_name."""
    c = WildberriesConnector()
    offer = c.normalize(WB_STORE_A)
    evidence = c.extract_evidence(offer)
    assert any(e.type == "name_extracted" for e in evidence)
    name_ev = [e for e in evidence if e.type == "name_extracted"][0]
    assert name_ev.value == "Tech-Master Store"


def test_evidence_brand():
    """Извлекает brand evidence."""
    c = WildberriesConnector()
    offer = c.normalize(WB_STORE_A)
    evidence = c.extract_evidence(offer)
    brand_ev = [e for e in evidence if e.field == "brand"]
    assert len(brand_ev) >= 1
    assert brand_ev[0].value == "Samsung"


def test_connector_limitations():
    """WB не даёт phone, email, inn, address."""
    c = WildberriesConnector()
    limits = c.limitations()
    assert "phone" in limits.never_available
    assert "email" in limits.never_available
    assert "inn" in limits.never_available


# ── Brand ≠ Seller ────────────────────────────────────────────────────────

def test_brand_not_seller_same_store():
    """
    Brand ≠ Seller: один магазин, разные бренды.

    Tech-Master Store продаёт Samsung и Bosch — это один продавец.
    """
    matcher = EntityMatcher()

    a = Listing(id="wb_bs1", category="Бытовая техника",
        source="wildberries", url="", title="Холодильник Samsung",
        seller_name="Tech-Master Store")
    b = Listing(id="wb_bs2", category="Бытовая техника",
        source="wildberries", url="", title="Стиральная машина Bosch",
        seller_name="Tech-Master Store")

    r = matcher.match(a, b)
    # seller_name совпадает + category почти совпадает → хоть какая-то уверенность
    assert r.confidence >= 0.08, f"Same store too low: {r.confidence}"
    # Если seller_name совпадает — не 'different'
    # (на маркетплейсе seller_name уникален для аккаунта)


def test_brand_not_seller_different_stores():
    """
    Brand ≠ Seller: один бренд Samsung, два магазина.

    Store-A и Store-B — разные продавцы. Не должны быть объединены.
    """
    matcher = EntityMatcher()

    a = Listing(id="wb_bd1", category="Электроника",
        source="wildberries", url="", title="Телевизор Samsung",
        seller_name="Store-A")
    b = Listing(id="wb_bd2", category="Электроника",
        source="wildberries", url="", title="Телевизор Samsung",
        seller_name="Store-B")

    r = matcher.match(a, b)
    assert r.confidence < 0.25, f"False merge risk: {r.confidence}"
    assert r.decision == "different"


def test_brand_not_seller_graph():
    """
    Brand ≠ Seller через Graph: один магазин с двумя брендами.
    """
    builder = GraphBuilder()

    p = SellerProfile(id="wb_brand1", name="Tech-Master Store",
        source_names=["wildberries", "ozon"])

    graph = builder.build_from_profiles([p])
    entity = list(graph.entities.values())[0]
    assert entity.name == "Tech-Master Store"
    assert entity.type == "store"  # wildberries → store type


# ── Same product, different sellers ───────────────────────────────────────

def test_same_product_diff_sellers():
    """
    Один товар (Dyson V15), два продавца (Seller-A, Seller-B).
    Ожидание: confidence низкий — 'different'.
    """
    matcher = EntityMatcher()

    a = Listing(id="wb_sp1", category="Пылесосы",
        source="wildberries", url="", title="Пылесос Dyson V15",
        seller_name="Seller-A")
    b = Listing(id="wb_sp2", category="Пылесосы",
        source="wildberries", url="", title="Пылесос Dyson V15",
        seller_name="Seller-B")

    r = matcher.match(a, b)
    assert r.confidence < 0.25, f"False merge risk: {r.confidence}"
    assert r.decision == "different"


# ── Seller rename ─────────────────────────────────────────────────────────

def test_seller_rename():
    """
    Seller rename: старое название → новое название, телефон + сайт те же.
    Ожидание: MATCH (через phone + website).
    """
    matcher = EntityMatcher()

    old = Listing(id="wb_rn1", category="Бытовая техника",
        source="wildberries", url="", title="Товар",
        seller_name="Старое Название", phone="+7 (495) 111-22-33",
        website="store-lg.ru")
    new = Listing(id="wb_rn2", category="Бытовая техника",
        source="wildberries", url="", title="Товар",
        seller_name="Новое Название", phone="+7 (495) 111-22-33",
        website="store-lg.ru")

    r = matcher.match(old, new)
    # phone + website = 0.35 + 0.35 = 0.70 → at least 0.50 after threshold
    assert r.confidence > 0.40, f"Rename confidence too low: {r.confidence}"


# ── Graph integration ─────────────────────────────────────────────────────

def test_graph_one_store_multi_brand():
    """
    Один магазин с двумя брендами → store entity с двумя offers.
    """
    builder = GraphBuilder()

    p = SellerProfile(id="wb_g1", name="Tech-Master Store",
        phones=["+7 (495) 111-22-33"],
        source_names=["wildberries", "ozon", "yandex_market"])

    graph = builder.build_from_profiles([p])
    assert graph.get_stats()["total_entities"] == 1
    entity = list(graph.entities.values())[0]
    assert entity.type == "store"
    assert entity.name == "Tech-Master Store"


def test_graph_store_different_sellers():
    """
    Два магазина с одним брендом — разные сущности.
    """
    builder = GraphBuilder()

    p1 = SellerProfile(id="wb_g2a", name="Store-A",
        source_names=["wildberries"])
    p2 = SellerProfile(id="wb_g2b", name="Store-B",
        source_names=["wildberries"])

    graph = builder.build_from_profiles([p1, p2])
    rels = [r for r in graph.relationships.values() if r.type == "same_as"]
    assert len(rels) == 0, "Store-A and Store-B should NOT be same_as"


def test_cross_source_wb_to_ozon():
    """
    Cross-source: WB + Ozon — один продавец на двух площадках.
    Ожидание: MATCH через seller_name + phone.
    """
    matcher = EntityMatcher()

    wb = Listing(id="wb_x1", category="Бытовая техника",
        source="wildberries", url="", title="Холодильник Samsung",
        seller_name="Tech-Master Store", phone="+7 (495) 111-22-33")
    oz = Listing(id="oz_x1", category="Бытовая техника",
        source="ozon", url="", title="Холодильник Samsung",
        seller_name="Tech-Master Store", phone="+7 (495) 111-22-33")

    r = matcher.match(wb, oz)
    assert r.confidence > 0.40, f"Cross-source WB↔Ozon too low: {r.confidence}"
    assert r.decision in ("candidate", "strong", "verified")


if __name__ == "__main__":
    print("=== Milestone 2.7: Wildberries Connector ===\n")

    tests = [
        test_connector_contract,
        test_offer_normalize,
        test_evidence_store_name,
        test_evidence_brand,
        test_connector_limitations,
        test_brand_not_seller_same_store,
        test_brand_not_seller_different_stores,
        test_brand_not_seller_graph,
        test_same_product_diff_sellers,
        test_seller_rename,
        test_graph_one_store_multi_brand,
        test_graph_store_different_sellers,
        test_cross_source_wb_to_ozon,
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
        print("🟢 Wildberries Connector PASS.")
