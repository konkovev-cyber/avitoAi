"""
Milestone 3.1 — Tests: Market Intelligence Report Engine.

Проверяет:
  1. SellerScorer — Visibility Score
  2. SellerScorer — top players ranking
  3. MarketScorer — market summary
  4. MarketScorer — opportunity signals
  5. MarketReport — полный отчёт
  6. Golden Dataset — отчёт по Стиркому + Либхерру
  7. Пустой граф — корректная обработка
"""

from ..intelligence.scorer import SellerScorer, MarketScorer
from ..intelligence.report import MarketReport
from ..graph.models import GraphEntity, Relationship, MarketGraph
from ..graph.builder import GraphBuilder
from ..models.seller import SellerProfile


# ── Fixtures ──────────────────────────────────────────────────────────────

def _make_graph_with_sellers() -> MarketGraph:
    """Построить тестовый граф с несколькими продавцами."""
    graph = MarketGraph()

    # Seller A — company, verified, 4 sources
    a = GraphEntity(id="entity_company_a", type="company", name="ООО Техно",
        phone="+7 (495) 111-11-11", website="techno.ru", inn="1234567890",
        status="verified", evidence_ids=["e1", "e2", "e3", "e4"],
        source_listing_ids=["ym_001", "av_001", "oz_001", "site_001"])
    graph.add_entity(a)

    # Seller B — store, verified, 2 sources
    b = GraphEntity(id="entity_store_b", type="store", name="Tech-Store",
        phone="+7 (495) 222-22-22", status="verified",
        evidence_ids=["e5", "e6"],
        source_listing_ids=["oz_002", "wb_001"])
    graph.add_entity(b)

    # Seller C — seller, candidate, 1 source
    c = GraphEntity(id="entity_seller_c", type="seller", name="Мастер Сергей",
        status="candidate", evidence_ids=["e7"],
        source_listing_ids=["av_002"])
    graph.add_entity(c)

    # Relationship A↔B
    graph.add_relationship(Relationship(
        id="rel_same_as_a_b", type="same_as",
        source_id="entity_company_a", target_id="entity_store_b",
        confidence=0.70,
    ))

    return graph


# ── SellerScorer Tests ────────────────────────────────────────────────────

def test_visibility_score_full():
    """Полный Visibility Score для компании с 4 источниками."""
    graph = _make_graph_with_sellers()
    entity = graph.get_entity("entity_company_a")
    scorer = SellerScorer()
    result = scorer.visibility_score(entity, graph)

    assert result["total_score"] > 50
    assert result["name"] == "ООО Техно"
    assert result["source_count"] >= 3
    assert result["evidence_count"] >= 4
    assert "source_yandex_maps" in result["breakdown"]
    assert "source_avito" in result["breakdown"]
    assert "has_phone" in result["breakdown"]
    assert "has_inn" in result["breakdown"]
    assert "has_website" in result["breakdown"]


def test_visibility_score_minimal():
    """Visibility Score для частника с 1 источником."""
    graph = _make_graph_with_sellers()
    entity = graph.get_entity("entity_seller_c")
    scorer = SellerScorer()
    result = scorer.visibility_score(entity, graph)

    assert result["total_score"] < 50  # низкий
    assert result["source_count"] == 1
    assert result["evidence_count"] == 1
    assert result["relationship_count"] == 0


def test_top_players():
    """Top 3 ранжированы по Score."""
    graph = _make_graph_with_sellers()
    scorer = SellerScorer()
    all_scores = [scorer.visibility_score(e, graph) for e in graph.entities.values()]
    top3 = scorer.top_players(all_scores, 3)

    assert len(top3) == 3
    # Самая высокая → первая
    assert top3[0]["total_score"] >= top3[1]["total_score"] >= top3[2]["total_score"]


def test_visibility_rank():
    """Ранжирование работает корректно."""
    graph = _make_graph_with_sellers()
    scorer = SellerScorer()
    results = [scorer.visibility_score(e, graph) for e in graph.entities.values()]
    ranked = scorer.visibility_rank(results)

    assert len(ranked) == 3
    assert ranked[0]["name"] == "ООО Техно"  # 4 sources


# ── MarketScorer Tests ────────────────────────────────────────────────────

def test_market_summary():
    """Общая статистика рынка."""
    graph = _make_graph_with_sellers()
    scorer = MarketScorer()
    summary = scorer.market_summary(graph)

    assert summary["total_entities"] == 3
    assert summary["total_relationships"] == 1
    assert summary["verified"] == 2
    assert summary["with_phone"] == 2
    assert summary["with_website"] == 1
    assert summary["with_inn"] == 1


def test_opportunity_signals():
    """Находит возможности: отсутствие сайта, 1 источник."""
    graph = _make_graph_with_sellers()
    scorer = MarketScorer()
    signals = scorer.opportunity_signals(graph)

    assert len(signals) >= 2
    types = [s["type"] for s in signals]
    assert "missing_website" in types
    assert "single_source" in types


def test_opportunity_missing_phone():
    """Сигнал: продавец без телефона."""
    graph = MarketGraph()
    graph.add_entity(GraphEntity(
        id="e_no_phone", type="seller", name="Мастер без телефона",
        status="verified", source_listing_ids=["av_001"],
    ))

    scorer = MarketScorer()
    signals = scorer.opportunity_signals(graph)
    types = [s["type"] for s in signals]
    assert any("phone" in t for t in types)


# ── MarketReport Tests ────────────────────────────────────────────────────

def test_report_generation():
    """Отчёт формируется из графа."""
    graph = _make_graph_with_sellers()
    report = MarketReport()
    text = report.generate(graph)

    assert "Market Intelligence Report" in text
    assert "Обзор рынка" in text
    assert "Топ участников" in text
    assert "Найденные возможности" in text
    assert "ООО Техно" in text
    assert "Мастер Сергей" in text
    assert "Evidence First" in text


def test_report_empty_graph():
    """Пустой граф — корректный отчёт."""
    graph = MarketGraph()
    report = MarketReport()
    text = report.generate(graph)

    assert "Market Intelligence Report" in text
    assert "Обзор рынка" in text
    assert "Нет данных" in text or "Участников" in text


def test_golden_dataset_report():
    """
    Golden Dataset: построить граф из профилей и сформировать отчёт.
    Использует Стирком.ру + Либхерр.
    """
    builder = GraphBuilder()

    p1 = SellerProfile(id="gd_p1", name="Стирком.ру",
        phones=["+7 (915) 338-18-07"], websites=["stirkom.ru"],
        addresses=["Жуковский"], source_names=["yandex_maps", "company_website"],
        listing_ids=["ym_005", "site_009"], evidence_ids=["e1", "e2", "e3"])
    p2 = SellerProfile(id="gd_p2", name="Либхерр Сервис",
        phones=["+7 495 797 12 17"], websites=["liebherr-service.ru"],
        inn="510704817991",
        source_names=["yandex_maps", "company_website"],
        listing_ids=["ym_001", "site_011", "site_012"],
        evidence_ids=["e9", "e10", "e11", "e12"])

    graph = builder.build_from_profiles([p1, p2])
    report = MarketReport()
    text = report.generate(graph)

    assert "Market Intelligence Report" in text
    assert "Стирком" in text or "stirkom" in text
    assert "Либхерр" in text or "Liebherr" in text
    assert "возможности" in text.lower()
    # Каждый вывод подкреплён Evidence
    assert "Доказательств" in text or "Tracked" in text


if __name__ == "__main__":
    print("=== Milestone 3.1: Market Intelligence Report ===\n")

    tests = [
        test_visibility_score_full,
        test_visibility_score_minimal,
        test_top_players,
        test_visibility_rank,
        test_market_summary,
        test_opportunity_signals,
        test_opportunity_missing_phone,
        test_report_generation,
        test_report_empty_graph,
        test_golden_dataset_report,
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
        print("🟢 Market Intelligence Report PASS.")
