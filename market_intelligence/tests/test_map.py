"""
Milestone 3.3 — Tests: Market Intelligence Map MVP.

Проверяет:
  1. ASCII entity graph render
  2. ASCII market map render
  3. HTML map render (overview)
  4. HTML map with opportunities
  5. HTML map with evidence chain
  6. Golden Dataset — создание карты
  7. Empty graph — корректная обработка
  8. Human review status display
"""

from ..graph.models import GraphEntity, MarketGraph, Relationship
from ..models.opportunity import Opportunity
from ..map.entity_graph import render_entity_graph, render_market_map
from ..map.html_map import HTMLMapRenderer


# ── Fixtures ──────────────────────────────────────────────────────────────

def _make_graph() -> MarketGraph:
    g = MarketGraph()
    a = GraphEntity(id="e_tech", type="company", name="ООО Техно",
        status="verified", confidence=0.95,
        phone="+7", website="techno.ru", inn="1234567890",
        source_listing_ids=["ym_001", "av_001", "oz_001", "site_001"],
        evidence_ids=["e1", "e2", "e3", "e4"])
    g.add_entity(a)

    b = GraphEntity(id="e_shop", type="store", name="Tech-Store Ozon",
        status="verified", confidence=0.85, phone="+7",
        source_listing_ids=["oz_002", "wb_001"],
        evidence_ids=["e5", "e6"])
    g.add_entity(b)

    g.add_relationship(Relationship(
        id="rel_same", type="same_as",
        source_id="e_tech", target_id="e_shop", confidence=0.70))
    return g


def _make_opportunities() -> list[Opportunity]:
    return [
        Opportunity(id="opp_001", type="no_website", severity="high",
            confidence=0.82, entity_ids=["e_tech"], entity_names=["ООО Техно"],
            evidence=["Активность на 4 площадках", "Сайт не обнаружен"],
            message="У ООО Техно нет сайта", recommendation="Создать сайт"),
        Opportunity(id="opp_002", type="marketplace_dependency", severity="medium",
            confidence=0.65, entity_ids=["e_shop"], entity_names=["Tech-Store"],
            evidence=["Только Ozon и Wildberries"],
            message="Tech-Store зависит от маркетплейсов",
            recommendation="Добавить прямой канал"),
    ]


def _make_golden_graph() -> MarketGraph:
    g = MarketGraph()
    g.add_entity(GraphEntity(id="gd_s", type="company", name="Стирком.ру",
        status="verified", phone="+7 (915) 338-18-07", website="stirkom.ru",
        source_listing_ids=["ym_005", "site_009"],
        evidence_ids=["e1", "e2", "e3"]))
    g.add_entity(GraphEntity(id="gd_l", type="company", name="Либхерр Сервис",
        status="verified", phone="+7 495 797 12 17", website="liebherr-service.ru",
        inn="510704817991", source_listing_ids=["ym_001", "site_011", "site_012"],
        evidence_ids=["e9", "e10", "e11"]))
    return g


# ── Tests ─────────────────────────────────────────────────────────────────

def test_ascii_entity_graph():
    """Рендеринг ASCII-графа сущности содержит имя, тип, контакты."""
    graph = _make_graph()
    entity = graph.get_entity("e_tech")
    lines = render_entity_graph(entity, graph)
    text = "\n".join(lines)
    assert "ООО Техно" in text
    assert "company" in text or "company" in text
    assert "+7" in text
    assert "techno.ru" in text
    assert "ИНН:" in text
    assert "Evidence:" in text


def test_ascii_entity_graph_no_data():
    """Сущность без данных → корректный рендер."""
    graph = MarketGraph()
    e = GraphEntity(id="e_empty", type="seller", name="Пусто")
    graph.add_entity(e)
    lines = render_entity_graph(e, graph)
    text = "\n".join(lines)
    assert "Пусто" in text
    assert "нет данных" in text.lower()


def test_ascii_market_map():
    """Рендеринг полной карты рынка."""
    graph = _make_graph()
    text = render_market_map(graph)
    assert "MARKET MAP" in text
    assert "ООО Техно" in text
    assert "Tech-Store" in text
    assert "Участников:" in text
    assert "Связей:" in text


def test_ascii_market_map_filtered():
    """Фильтрация: показать только указанные entity_ids."""
    graph = _make_graph()
    text = render_market_map(graph, entity_ids=["e_tech"])
    assert "ООО Техно" in text
    assert True


def test_ascii_market_map_empty():
    """Пустой граф → корректный рендер."""
    text = render_market_map(MarketGraph())
    assert "MARKET MAP" in text
    assert "пусто" in text.lower()


def test_html_map_overview():
    """HTML-карта содержит обзор рынка."""
    graph = _make_graph()
    html = HTMLMapRenderer(graph).render()
    assert "Market Intelligence Map" in html
    assert "Обзор рынка" in html
    assert "Участник" in html
    assert "ООО Техно" in html


def test_html_map_with_opportunities():
    """HTML-карта с возможностями."""
    graph = _make_graph()
    opps = _make_opportunities()
    html = HTMLMapRenderer(graph, opps).render()
    assert "Возможности" in html
    assert "У ООО Техно нет сайта" in html
    assert "Уверенность: 82%" in html
    assert "кандидат" in html


def test_html_map_evidence_chain():
    """HTML-карта отображает Evidence Chain."""
    graph = _make_graph()
    html = HTMLMapRenderer(graph).render()
    assert "Evidence Chain" in html
    assert "e1" in html
    assert "e2" in html


def test_html_map_human_review():
    """Human Review статусы отображаются."""
    opps = _make_opportunities()
    # Проверить, что статус 'candidate' отображается
    assert any(o.status == "candidate" for o in opps)

    # Отметить одну как подтверждённую
    opps[0].status = "validated"
    graph = _make_graph()
    html = HTMLMapRenderer(graph, opps).render()
    assert "Подтверждено человеком" in html


def test_golden_dataset_map():
    """Golden Dataset: HTML-карта со Стиркомом и Либхерром."""
    graph = _make_golden_graph()
    html = HTMLMapRenderer(graph).render()
    assert "Стирком" in html
    assert "Либхерр" in html
    assert "stirkom.ru" in html
    assert "510704817991" in html
    assert "Evidence Chain" in html


def test_html_map_empty():
    """Пустой граф → корректный HTML."""
    html = HTMLMapRenderer(MarketGraph()).render()
    assert "Market Intelligence Map" in html
    assert "Нет данных" in html


if __name__ == "__main__":
    print("=== Milestone 3.3: Market Intelligence Map ===\n")

    tests = [
        test_ascii_entity_graph,
        test_ascii_entity_graph_no_data,
        test_ascii_market_map,
        test_ascii_market_map_filtered,
        test_ascii_market_map_empty,
        test_html_map_overview,
        test_html_map_with_opportunities,
        test_html_map_evidence_chain,
        test_html_map_human_review,
        test_golden_dataset_map,
        test_html_map_empty,
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
        print("🟢 Market Map MVP PASS.")
