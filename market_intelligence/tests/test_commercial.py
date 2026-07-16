"""
Milestone 4.1 — Tests: First Commercial Intelligence Scenario.

Проверяет:
  1. Lead model
  2. Lead Generator — RULE_001 (Digital Expansion)
  3. Lead Generator — RULE_002 (Channel Diversification)
  4. Lead Generator — RULE_003 (Growth Opportunity)
  5. Lead Score — объяснимость
  6. No evidence → no lead
  7. False recommendation protection
  8. Recommendation generation
  9. Commercial report
  10. Golden Dataset — реальные лиды
"""

from ..models.lead import Lead
from ..graph.models import GraphEntity, MarketGraph
from ..intelligence.commercial.lead_generator import LeadGenerator
from ..intelligence.commercial.lead_score import LeadScorer
from ..intelligence.commercial.recommendation import get_recommendation, generate_commercial_report
from .test_intelligence import _make_graph_with_sellers


# ── Model Tests ───────────────────────────────────────────────────────────

def test_lead_model():
    """Lead создаётся с минимальными полями."""
    l = Lead(
        id="lead_test_001",
        type="digital_expansion",
        score=82,
        entity_id="e1",
        entity_name="ООО Тест",
        evidence=["Нет сайта", "Есть на Avito"],
        recommended_action="Создать сайт",
    )
    assert l.id == "lead_test_001"
    assert l.score == 82
    assert l.has_evidence
    assert l.is_actionable
    assert l.status == "new"


def test_lead_low_score():
    """Низкий score → не actionable."""
    l = Lead(id="lead_low", type="digital_expansion", score=35,
             entity_id="e1", entity_name="Тест")
    assert l.is_actionable is False


# ── RULE_001: Digital Expansion ───────────────────────────────────────────

def test_rule_digital_expansion():
    """
    RULE_001: Verified seller + no website + multiple sources → Digital Expansion Lead.
    """
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_rule1", type="company", name="ООО Техно",
        status="verified", source_listing_ids=["ym_001", "av_001", "oz_001"],
        evidence_ids=["e1", "e2"]))

    gen = LeadGenerator()
    leads = gen.generate(g)
    types = [l.type for l in leads]
    assert "digital_expansion" in types

    lead = [l for l in leads if l.type == "digital_expansion"][0]
    assert lead.entity_name == "ООО Техно"
    assert lead.has_evidence
    assert lead.rules_triggered


# ── RULE_002: Channel Diversification ─────────────────────────────────────

def test_rule_channel_diversification():
    """
    RULE_002: Marketplace seller + no owned channel → Channel Diversification Lead.
    """
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_rule2", type="store", name="Ozon Shop",
        status="verified", phone="+7 (495) 111-22-33",
        source_listing_ids=["oz_001", "oz_002"]))

    gen = LeadGenerator()
    leads = gen.generate(g)
    types = [l.type for l in leads]
    assert "channel_diversification" in types


# ── RULE_003: Growth Opportunity ──────────────────────────────────────────

def test_rule_growth_opportunity():
    """
    RULE_003: High activity + weak presence → Growth Opportunity Lead.
    """
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_rule3", type="seller", name="Мастер",
        status="verified", phone="+7 (495) 111-22-33",
        source_listing_ids=["oz_001", "oz_002", "oz_003"]))

    gen = LeadGenerator()
    leads = gen.generate(g)
    types = [l.type for l in leads]
    assert "growth_opportunity" in types or "expansion_opportunity" in types


# ── Lead Score ────────────────────────────────────────────────────────────

def test_lead_score_explainable():
    """Lead Score имеет разложение по компонентам."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_score", type="company", name="ООО Тест",
        status="verified", phone="+7 (495) 111-22-33",
        source_listing_ids=["ym_001", "av_001", "oz_001", "site_001"],
        evidence_ids=["e1", "e2", "e3", "e4"]))

    gen = LeadGenerator()
    leads = gen.generate(g)

    for lead in leads:
        assert lead.score > 0, f"Lead {lead.id} has zero score"
        assert len(lead.score_breakdown) >= 1, f"Lead {lead.id} has no breakdown"


def test_lead_score_explainable_text():
    """Score breakdown формируется в читаемый текст."""
    scorer = LeadScorer()
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_exp", type="company", name="ООО Эксплейн",
        status="verified", phone="+7 (495) 111-22-33",
        source_listing_ids=["ym_001", "av_001"],
        evidence_ids=["e1", "e2"]))

    lead = Lead(id="lead_exp", type="digital_expansion", score=50,
                entity_id="e_exp", entity_name="ООО Эксплейн",
                evidence=["Нет сайта"], recommended_action="Создать сайт")
    scorer.score(lead, g)

    text = LeadScorer.explain(lead)
    assert "Lead Score" in text
    assert str(lead.score) in text
    assert "Evidence" in text
    assert "Рекомендация" in text


# ── No Evidence → No Lead ────────────────────────────────────────────────

def test_no_evidence_no_lead():
    """Без evidence → без лида."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_noop", type="company", name="Тишина",
        status="hypothesis"))

    gen = LeadGenerator()
    leads = gen.generate(g)
    assert len(leads) == 0


# ── False Recommendation Protection ───────────────────────────────────────

def test_false_recommendation_protection():
    """
    Слабая гипотеза → лид не создаётся.
    """
    g = MarketGraph()
    g.add_entity(GraphEntity(id="e_weak", type="seller", name="Слабая гипотеза",
        status="hypothesis", source_listing_ids=["ym_001"]))

    gen = LeadGenerator()
    leads = gen.generate(g)
    # Ни одно правило не должно сработать на слабой гипотезе
    assert len(leads) == 0


# ── Recommendation ────────────────────────────────────────────────────────

def test_recommendation_generation():
    """Рекомендация формируется из Lead."""
    l = Lead(id="lead_rec", type="digital_expansion", score=82,
             entity_id="e1", entity_name="ООО Техно",
             evidence=["Нет сайта"], recommended_action="Создать сайт")

    rec = get_recommendation(l)
    assert rec["lead_id"] == "lead_rec"
    assert rec["target"] == "ООО Техно"
    assert rec["label"] == "Цифровая экспансия"
    assert rec["automated"] is False
    assert len(rec["next_steps"]) >= 1


def test_commercial_report():
    """Коммерческий отчёт формируется."""
    leads = [
        Lead(id="l1", type="digital_expansion", score=82,
             entity_id="e1", entity_name="ООО Техно", status="new",
             evidence=["Нет сайта"], recommended_action="Создать сайт", priority="high"),
        Lead(id="l2", type="channel_diversification", score=45,
             entity_id="e2", entity_name="Ozon Shop", status="new",
             evidence=["Только Ozon"], recommended_action="Диверсификация"),
    ]

    report = generate_commercial_report(leads)
    assert "COMMERCIAL INTELLIGENCE REPORT" in report
    assert "ООО Техно" in report
    assert "ПРИОРИТЕТНЫЕ" in report


# ── Golden Dataset ────────────────────────────────────────────────────────

def test_golden_dataset_leads():
    """Golden Dataset: Стирком + Либхерр → лиды."""
    g = MarketGraph()
    g.add_entity(GraphEntity(id="gd_s", type="company", name="Стирком.ру",
        status="verified", phone="+7 (915) 338-18-07", website="stirkom.ru",
        source_listing_ids=["ym_005", "site_009"],
        evidence_ids=["e1", "e2", "e3"]))
    g.add_entity(GraphEntity(id="gd_l", type="company", name="Либхерр Сервис",
        status="verified", phone="+7 495 797 12 17", website="liebherr-service.ru",
        inn="510704817991", source_listing_ids=["ym_001", "site_011", "site_012"],
        evidence_ids=["e9", "e10", "e11"]))

    gen = LeadGenerator()
    leads = gen.generate(g)

    # Оба имеют phone + website → Digital Expansion НЕ должен быть
    digital = [l for l in leads if l.type == "digital_expansion"]
    assert len(digital) == 0, "Golden entities have websites — no digital expansion leads"

    # Check every lead has evidence
    for l in leads:
        assert l.has_evidence, f"Lead {l.id} has no evidence"
        assert l.score > 0, f"Lead {l.id} has zero score"


if __name__ == "__main__":
    print("=== Milestone 4.1: Commercial Intelligence ===\n")

    tests = [
        test_lead_model,
        test_lead_low_score,
        test_rule_digital_expansion,
        test_rule_channel_diversification,
        test_rule_growth_opportunity,
        test_lead_score_explainable,
        test_lead_score_explainable_text,
        test_no_evidence_no_lead,
        test_false_recommendation_protection,
        test_recommendation_generation,
        test_commercial_report,
        test_golden_dataset_leads,
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
        print("🟢 Commercial Intelligence PASS.")
