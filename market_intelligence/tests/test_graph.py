"""
Milestone 2.4 — Tests: Market Graph MVP.

Проверяет:
  1. GraphEntity создание
  2. Relationship создание
  3. MarketGraph операции (add, find, merge)
  4. GraphBuilder из профилей
  5. same_as связи между похожими профилями
  6. Триангуляция через граф (Golden Dataset воспроизводимость)
"""

from ..graph.models import GraphEntity, Relationship, MarketGraph
from ..graph.builder import GraphBuilder
from ..models.seller import SellerProfile
from ..models.listing import Listing


# ── Basic Graph Tests ─────────────────────────────────────────────────────

def test_entity_creation():
    """Создание GraphEntity с минимальными полями."""
    e = GraphEntity(
        id="entity_seller_test",
        type="seller",
        name="Тестовый мастер",
    )
    assert e.id == "entity_seller_test"
    assert e.type == "seller"
    assert e.status == "hypothesis"
    assert e.confidence == 0.0


def test_entity_with_details():
    """GraphEntity с контактами и confidence."""
    e = GraphEntity(
        id="entity_company_holod",
        type="company",
        name="Холод-Сервис",
        inn="7810674120",
        phone="+7 (495) 111-22-33",
        website="holod-service.ru",
        confidence=0.95,
        status="verified",
        source_listing_ids=["L0001", "L0010"],
    )
    assert e.inn == "7810674120"
    assert e.confidence == 0.95
    assert e.status == "verified"
    assert len(e.source_listing_ids) == 2


def test_entity_hash():
    """Entity хэшируется по id."""
    e1 = GraphEntity(id="e1", type="seller", name="A")
    e2 = GraphEntity(id="e1", type="seller", name="A")
    assert e1 == e2
    assert hash(e1) == hash(e2)


def test_relationship_creation():
    """Создание Relationship."""
    rel = Relationship(
        id="rel_same_as_a_b",
        type="same_as",
        source_id="entity_seller_a",
        target_id="entity_seller_b",
        confidence=0.85,
        evidence=["phone_match", "website_match"],
    )
    assert rel.type == "same_as"
    assert rel.confidence == 0.85
    assert len(rel.evidence) == 2


def test_market_graph_add_find():
    """Добавление и поиск сущностей в графе."""
    graph = MarketGraph()

    e1 = GraphEntity(id="e1", type="seller", name="Мастер Сергей")
    e2 = GraphEntity(id="e2", type="company", name="ООО Сервис")
    graph.add_entity(e1)
    graph.add_entity(e2)

    assert graph.get_entity("e1") == e1
    assert len(graph.find_entity("Сергей")) == 1
    assert len(graph.find_entity("Сервис")) == 1
    assert len(graph.find_entity("Сергей", entity_type="seller")) == 1


def test_market_graph_stats():
    """Статистика графа."""
    graph = MarketGraph()
    graph.add_entity(GraphEntity(id="e1", type="seller", name="A", status="verified"))
    graph.add_entity(GraphEntity(id="e2", type="company", name="B", status="verified"))
    graph.add_entity(GraphEntity(id="e3", type="store", name="C"))

    stats = graph.get_stats()
    assert stats["total_entities"] == 3
    assert stats["verified_entities"] == 2


def test_market_graph_get_relationships():
    """Получение связей сущности."""
    graph = MarketGraph()
    e1 = GraphEntity(id="e1", type="seller", name="Мастер")
    e2 = GraphEntity(id="e2", type="company", name="Компания")
    graph.add_entity(e1)
    graph.add_entity(e2)

    rel = Relationship(
        id="rel_owns_e1_e2",
        type="same_as",
        source_id="e1",
        target_id="e2",
        confidence=0.80,
    )
    graph.add_relationship(rel)

    rels = graph.get_relationships("e1")
    assert len(rels) == 1
    assert rels[0].type == "same_as"


def test_market_graph_merge():
    """Объединение двух графов."""
    g1 = MarketGraph()
    g1.add_entity(GraphEntity(id="e1", type="seller", name="A"))

    g2 = MarketGraph()
    g2.add_entity(GraphEntity(id="e2", type="company", name="B"))

    g1.merge_graphs(g2)
    assert g1.get_entity("e1") is not None
    assert g1.get_entity("e2") is not None
    assert g1.get_stats()["total_entities"] == 2


# ── Graph Builder Tests ───────────────────────────────────────────────────

def test_builder_from_single_profile():
    """Один профиль → одна entity."""
    builder = GraphBuilder()
    profile = SellerProfile(
        id="seller_001",
        name="Тестовый Мастер",
        confidence=0.70,
        status="candidate",
        source_names=["avito"],
    )
    graph = builder.build_from_profiles([profile])
    assert graph.get_stats()["total_entities"] == 1
    entity = list(graph.entities.values())[0]
    assert entity.status == "candidate"


def test_builder_with_listings():
    """Профиль + Listing → entity + product + связь."""
    builder = GraphBuilder()
    profile = SellerProfile(
        id="seller_001",
        name="Мастер Иванов",
        confidence=0.70,
        status="candidate",
        source_names=["avito", "yandex_maps"],
    )
    listing = Listing(
        id="L001",
        source="avito",
        url="https://avito.ru/test",
        title="Ремонт холодильников",
        category="Ремонт бытовой техники",
        price=1500,
    )
    graph = builder.build_from_profiles([profile], listings=[listing])
    assert graph.get_stats()["total_entities"] >= 2  # seller + product
    rels = list(graph.relationships.values())
    assert any(r.type == "sells" for r in rels), "Missing sells relationship"


def test_builder_two_profiles_same():
    """
    Два похожих профиля → same_as relationship.

    Один телефон → связь создаётся.
    """
    builder = GraphBuilder()
    p1 = SellerProfile(
        id="seller_001",
        name="Стирком.ру",
        confidence=0.70,
        status="candidate",
        source_names=["yandex_maps"],
        phones=["+7 (915) 338-18-07"],
        websites=["stirkom.ru"],
    )
    p2 = SellerProfile(
        id="seller_002",
        name="СтирКом",
        confidence=0.70,
        status="candidate",
        source_names=["company_website"],
        phones=["+7 (915) 338-18-07"],
        websites=["stirkom.ru"],
    )
    graph = builder.build_from_profiles([p1, p2])
    rels = list(graph.relationships.values())
    same_as = [r for r in rels if r.type == "same_as"]
    assert len(same_as) >= 1, "Expected same_as relationship"


def test_builder_two_profiles_different():
    """
    Два разных профиля → без same_as (confidence низкий).

    Разные телефоны, разные города.
    """
    builder = GraphBuilder()
    p1 = SellerProfile(
        id="seller_001",
        name="Импорт-Сервис",
        phones=["+7 (495) 111-11-11"],
        addresses=["Лыткарино"],
        source_names=["yandex_maps"],
    )
    p2 = SellerProfile(
        id="seller_002",
        name="Импорт-Сервис",
        phones=["8 (812) 702-33-33"],
        websites=["import-service.ru"],
        addresses=["Санкт-Петербург"],
        source_names=["company_website"],
    )
    graph = builder.build_from_profiles([p1, p2])
    rels = list(graph.relationships.values())
    same_as = [r for r in rels if r.type == "same_as"]
    assert len(same_as) == 0, "False same_as created!"


def test_golden_dataset_stirkom_graph():
    """
    Golden Dataset: Стирком.ру.

    Три Listing → два профиля → one seller entity.
    2 источника: Яндекс Карты + сайт.
    """
    builder = GraphBuilder()

    p1 = SellerProfile(
        id="seller_005",
        name="Стирком.ру",
        confidence=0.80,
        status="verified",
        phones=["+7 (915) 338-18-07"],
        websites=["stirkom.ru"],
        addresses=["Жуковский, Кооперативная ул., 3"],
        source_names=["yandex_maps"],
        listing_ids=["L0005"],
    )
    p2 = SellerProfile(
        id="seller_007",
        name="СтирКом",
        confidence=0.95,
        status="verified",
        phones=["+7 (915) 338-18-07"],
        emails=["stirkom1@yandex.ru"],
        websites=["stirkom.ru"],
        addresses=["Жуковский, Кооперативная ул., 3"],
        source_names=["company_website"],
        listing_ids=["L0009"],
    )

    graph = builder.build_from_profiles([p1, p2])
    rels = list(graph.relationships.values())
    same_as = [r for r in rels if r.type == "same_as"]
    has_link = len(same_as) >= 1
    assert has_link, f"Stirkom should have same_as link. Rels: {[r.type for r in rels]}"


def test_golden_dataset_liebherr_graph():
    """
    Golden Dataset: Либхерр.

    L0001 (Карты) + L0011 (сайт) + L0012 (реквизиты).
    """
    builder = GraphBuilder()

    p1 = SellerProfile(
        id="seller_001",
        name="Либхерр Сервис",
        confidence=0.70,
        source_names=["yandex_maps"],
        phones=["+7 495 797 12 17"],
        websites=["liebherr-service.ru"],
        addresses=["Москва, Салтыковская ул., 51"],
        listing_ids=["L0001"],
    )
    p2 = SellerProfile(
        id="seller_001_website",
        name="Сервисный центр Liebherr",
        confidence=0.95,
        status="verified",
        phones=["+7 495 797 12 17"],
        emails=["liebherr-service@internet.ru"],
        websites=["liebherr-service.ru"],
        addresses=["Москва, ул. Перерва, 11"],
        inn="510704817991",
        source_names=["company_website"],
        listing_ids=["L0011", "L0012"],
    )

    graph = builder.build_from_profiles([p1, p2])
    rels = list(graph.relationships.values())
    same_as = [r for r in rels if r.type == "same_as"]
    unknown = [r for r in rels if r.type == "unknown"]
    has_link = len(same_as) + len(unknown) >= 1
    assert has_link, f"Liebherr should have at least one relationship. Rels: {[r.type for r in rels]}"


def test_graph_infer_entity_type():
    """Определение типа сущности по данным профиля."""
    builder = GraphBuilder()

    # Компания с ИНН
    p1 = SellerProfile(id="p1", name="ООО Тест", inn="1234567890")
    assert builder._infer_entity_type(p1) == "company"

    # Магазин с маркетплейса
    p2 = SellerProfile(id="p2", name="Магазин", source_names=["yandex_market", "company_website"])
    assert builder._infer_entity_type(p2) == "store"

    # Частник с Avito
    p3 = SellerProfile(id="p3", name="Сергей", source_names=["avito"])
    assert builder._infer_entity_type(p3) == "seller"


def test_graph_report():
    """Граф формирует читаемый отчёт."""
    builder = GraphBuilder()
    p1 = SellerProfile(id="p1", name="Тест", phones=["+7111"], source_names=["avito"])
    p2 = SellerProfile(id="p2", name="Тест2", phones=["+7111"], source_names=["yandex_maps"])
    graph = builder.build_from_profiles([p1, p2])
    report = builder.report(graph)
    assert "Market Graph Report" in report
    assert "Entities:" in report
    assert "Relationships:" in report


if __name__ == "__main__":
    print("=== Milestone 2.4: Market Graph MVP Tests ===\n")

    tests = [
        test_entity_creation,
        test_entity_with_details,
        test_entity_hash,
        test_relationship_creation,
        test_market_graph_add_find,
        test_market_graph_stats,
        test_market_graph_get_relationships,
        test_market_graph_merge,
        test_builder_from_single_profile,
        test_builder_with_listings,
        test_builder_two_profiles_same,
        test_builder_two_profiles_different,
        test_golden_dataset_stirkom_graph,
        test_golden_dataset_liebherr_graph,
        test_graph_infer_entity_type,
        test_graph_report,
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
