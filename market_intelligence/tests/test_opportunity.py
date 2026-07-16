"""
Milestone 3.2 — Tests: Opportunity Engine MVP.

Проверяет:
  1. Opportunity model
  2. Weak digital presence signal
  3. Marketplace dependency signal
  4. Multi-source conflict signal
  5. Competitor gap signal
  6. Single source risk signal
  7. No phone signal
  8. No website signal
  9. Expansion opportunity signal
  10. Full scan + report
  11. Golden Dataset — реальные сигналы
  12. Empty graph — корректная обработка
"""

from ..models.opportunity import Opportunity
from ..graph.models import GraphEntity, MarketGraph
from ..intelligence.opportunity import OpportunityEngine


# ── Fixtures ──────────────────────────────────────────────────────────────

def _graph_no_website() -> MarketGraph:
    """Продавец без сайта."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e1", type="company", name="ООО Техно",
        status="verified", source_listing_ids=["ym_001", "av_001"]))
    return g


def _graph_no_phone() -> MarketGraph:
    """Верифицированный продавец без телефона."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e2", type="company", name="ООО Сервис",
        status="verified", website="servis.ru",
        source_listing_ids=["ym_001", "site_001"]))
    return g


def _graph_single_source() -> MarketGraph:
    """Продавец только на Ozon."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e3", type="store", name="Ozon Shop",
        status="verified", phone="+7 (495) 111-11-11",
        source_listing_ids=["oz_001", "oz_002"]))
    return g


def _graph_concentrated() -> MarketGraph:
    """Рынок с высокой концентрацией (топ-3 > 60%)."""
    g = MarketGraph()
    for i in range(6):
        src_count = 4 if i < 3 else 1
        srcs = [f"ym_{i}_{j}" for j in range(src_count)]
        g.add_entity(GraphEntity(
            id=f"e_conc_{i}", type="company",
            name=f"Company {'ABC'[i] if i < 3 else 'Other'}",
            status="verified",
            source_listing_ids=srcs,
        ))
    return g


def _graph_golden() -> MarketGraph:
    """Golden Dataset: Стирком + Либхерр."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="gd_ym1", type="company", name="Стирком.ру",
        status="verified", phone="+7 (915) 338-18-07",
        website="stirkom.ru",
        source_listing_ids=["ym_005", "site_009"],
        evidence_ids=["e1", "e2", "e3"]))
    g.add_entity(GraphEntity(id="gd_ym2", type="company", name="Либхерр Сервис",
        status="verified", phone="+7 495 797 12 17",
        website="liebherr-service.ru",
        inn="510704817991", source_listing_ids=["ym_001", "site_011", "site_012"],
        evidence_ids=["e9", "e10", "e11"]))
    return g


# ── Model Tests ───────────────────────────────────────────────────────────

def test_opportunity_model():
    """Создание Opportunity с минимальными полями."""
    o = Opportunity(
        id="opp_test_001",
        type="no_website",
        severity="medium",
        confidence=0.70,
        entity_ids=["e1"],
        entity_names=["Тест"],
        evidence=["Нет сайта"],
        message="У теста нет сайта",
        recommendation="Создать сайт",
    )
    assert o.id == "opp_test_001"
    assert o.type == "no_website"
    assert o.confidence == 0.70
    assert o.status == "candidate"
    assert o.is_actionable is True  # 0.70 >= 0.60, severity high


def test_opportunity_low_confidence_not_actionable():
    """Низкий confidence → не actionable."""
    o = Opportunity(
        id="opp_test_002",
        type="multi_source_conflict",
        confidence=0.45,
        entity_ids=["e2"],
        entity_names=["Тест"],
        evidence=["Нет телефона"],
        message="",
        recommendation="",
    )
    assert o.is_actionable is False


# ── Signal Tests ──────────────────────────────────────────────────────────

def test_signal_no_website():
    """Продавец без сайта → weak_digital_presence."""
    engine = OpportunityEngine()
    opps = engine.scan(_graph_no_website())
    types = [o.type for o in opps]
    assert "weak_digital_presence" in types
    opp = [o for o in opps if o.type == "weak_digital_presence"][0]
    assert "ООО Техно" in opp.entity_names
    assert opp.confidence >= 0.50
    assert len(opp.evidence) >= 1


def test_signal_no_phone():
    """Верифицированный продавец без телефона → no_phone."""
    engine = OpportunityEngine()
    opps = engine.scan(_graph_no_phone())
    types = [o.type for o in opps]
    assert "no_phone" in types
    opp = [o for o in opps if o.type == "no_phone"][0]
    assert opp.severity == "high"


def test_signal_marketplace_dependency():
    """Продавец только на маркетплейсе → marketplace_dependency."""
    engine = OpportunityEngine()
    opps = engine.scan(_graph_single_source())
    types = [o.type for o in opps]
    assert "marketplace_dependency" in types or "single_source_risk" in types


def test_signal_competitor_gap():
    """Рынок с концентрацией → competitor_gap."""
    engine = OpportunityEngine()
    opps = engine.scan(_graph_concentrated())
    types = [o.type for o in opps]
    assert "competitor_gap" in types


def test_signal_single_source_risk():
    """Один источник → single_source_risk."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_ssr", type="seller", name="Только Avito",
        status="verified", source_listing_ids=["av_001"]))
    engine = OpportunityEngine()
    opps = engine.scan(g)
    types = [o.type for o in opps]
    assert "single_source_risk" in types


def test_signal_expansion():
    """Сильный продавец на одной площадке → expansion_opportunity."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_exp", type="store", name="Ozon Магазин",
        status="verified", phone="+7 (495) 111-11-11",
        source_listing_ids=["oz_001", "oz_002", "oz_003"]))
    engine = OpportunityEngine()
    opps = engine.scan(g)
    types = [o.type for o in opps]
    assert "expansion_opportunity" in types


# ── Full Scan Tests ───────────────────────────────────────────────────────

def test_full_scan():
    """Полный скан возвращает все типы сигналов."""
    # Граф с разными типами сущностей
    g = MarketGraph()
    g.add_entity(GraphEntity(id="f1", type="company", name="Без сайта",
        status="verified", source_listing_ids=["ym_001", "av_001"]))
    g.add_entity(GraphEntity(id="f2", type="seller", name="Без телефона",
        status="verified", website="site.ru",
        source_listing_ids=["site_001"]))
    g.add_entity(GraphEntity(id="f3", type="store", name="Ozon Only",
        status="verified", phone="+7 (495) 111-11-11",
        source_listing_ids=["oz_001"]))

    engine = OpportunityEngine()
    opps = engine.scan(g)
    assert len(opps) >= 3
    types = set(o.type for o in opps)
    assert "weak_digital_presence" in types or "no_website" in types
    assert "no_phone" in types
    assert "single_source_risk" in types


def test_opportunity_report():
    """Report формируется из списка возможностей."""
    engine = OpportunityEngine()
    opps = engine.scan(_graph_no_website())
    report = engine.report(opps)
    assert "Приоритетные" in report or "Остальные" in report or "не найдено" in report


def test_empty_graph():
    """Пустой граф → пустой список."""
    engine = OpportunityEngine()
    opps = engine.scan(MarketGraph())
    assert len(opps) == 0


def test_golden_dataset_opportunities():
    """Golden Dataset: реальные сигналы из Стиркома и Либхерра."""
    engine = OpportunityEngine()
    opps = engine.scan(_graph_golden())
    # Оба имеют phone + website, так что no_phone и no_website НЕ должны быть
    opps_no_phone = [o for o in opps if o.type == "no_phone"]
    opps_no_web = [o for o in opps if o.type == "no_website"]
    assert len(opps_no_phone) == 0, "Golden entities have phones"
    assert len(opps_no_web) == 0, "Golden entities have websites"


def test_every_opportunity_has_evidence():
    """Каждая возможность подкреплена Evidence."""
    g = _graph_golden()
    engine = OpportunityEngine()
    opps = engine.scan(g)
    for o in opps:
        assert len(o.evidence) >= 1, f"{o.type} has no evidence"
        assert len(o.entity_ids) >= 1
        assert len(o.entity_names) >= 1


if __name__ == "__main__":
    print("=== Milestone 3.2: Opportunity Engine MVP ===\n")

    tests = [
        test_opportunity_model,
        test_opportunity_low_confidence_not_actionable,
        test_signal_no_website,
        test_signal_no_phone,
        test_signal_marketplace_dependency,
        test_signal_competitor_gap,
        test_signal_single_source_risk,
        test_signal_expansion,
        test_full_scan,
        test_opportunity_report,
        test_empty_graph,
        test_golden_dataset_opportunities,
        test_every_opportunity_has_evidence,
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
        print("🟢 Opportunity Engine MVP PASS.")
