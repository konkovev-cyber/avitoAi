"""
Milestone 2.5 — Graph Stress Test.

10 кейсов, проверяющих Graph на конфликты:
   1. Один продавец, несколько витрин (Techno.ru, YM, Ozon)
   2. Одинаковый бренд, разные продавцы (Samsung Parts)
   3. Филиалы компании (Москва + СПб + Казань)
   4. Ребрендинг (старое → новое название)
   5. Положительное слияние — Стирком + Либхерр
   6. Магазин на 3 маркетплейсах
   7. Один телефон, разные имена (перекупы)
   8. Разные телефоны, один бренд, один город
   9. Пустые профили без контактов (×3)
  10. Частный мастер стал компанией
"""

from ..graph.models import GraphEntity, Relationship, MarketGraph
from ..graph.builder import GraphBuilder
from ..models.seller import SellerProfile
from ..models.listing import Listing
from ..resolution.matcher import EntityMatcher

builder = GraphBuilder()
matcher = EntityMatcher()


def result(name: str, passed: bool, detail: str = ""):
    status = "✅" if passed else "❌"
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))


# ── Case 1: One Seller, Multiple Storefronts ─────────────────────────────

def test_case_1_multi_storefront():
    """
    ООО Техно → 3 витрины: сайт, YM, Ozon.
    Все три — одна Entity (через телефон/сайт).
    """
    p1 = SellerProfile(id="s1", name="techno.ru",
        phones=["+7 (495) 111-22-33"], websites=["techno.ru"],
        source_names=["company_website"])
    p2 = SellerProfile(id="s2", name="Techno Official (YM)",
        phones=["+7 (495) 111-22-33"], websites=["techno.ru"],
        source_names=["yandex_market"])
    p3 = SellerProfile(id="s3", name="Techno Store (Ozon)",
        phones=["+7 (495) 111-22-33"], source_names=["ozon"])

    graph = builder.build_from_profiles([p1, p2, p3])
    rels = list(graph.relationships.values())
    has_links = len(rels) >= 2
    result("Case 1: Multi-storefront", has_links,
           f"{len(rels)} relationships" if has_links else "")
    return has_links


# ── Case 2: Same Brand, Different Sellers ────────────────────────────────

def test_case_2_same_brand_diff_sellers():
    """
    Samsung Parts: два продавца с одним брендом.
    Разные телефоны → разные Entity.
    """
    p1 = SellerProfile(id="s4", name="Samsung Parts Москва",
        phones=["+7 (495) 111-11-11"],
        source_names=["yandex_market", "ozon"])
    p2 = SellerProfile(id="s5", name="Samsung Parts СПб",
        phones=["+7 (812) 222-22-22"],
        source_names=["yandex_market", "wildberries"])

    graph = builder.build_from_profiles([p1, p2])
    rels = [r for r in graph.relationships.values() if r.type == "same_as"]
    no_false_merge = len(rels) == 0
    result("Case 2: Same brand, diff sellers", no_false_merge,
           f"{len(rels)} same_as (expect 0)")
    return no_false_merge


# ── Case 3: Branch / Franchise / Multi-city ──────────────────────────────

def test_case_3_franchise():
    """
    Компания X в 3 городах. Один сайт, один бренд.
    """
    p1 = SellerProfile(id="s6", name="Холод-Сервис Москва",
        phones=["+7 (495) 111-11-11"], websites=["holod-service.ru"],
        addresses=["Москва"], source_names=["yandex_maps"])
    p2 = SellerProfile(id="s7", name="Холод-Сервис СПб",
        phones=["+7 (812) 222-22-22"], websites=["holod-service.ru"],
        addresses=["Санкт-Петербург"], source_names=["yandex_maps"])
    p3 = SellerProfile(id="s8", name="Холод-Сервис Казань",
        phones=["+7 (843) 333-33-33"], websites=["holod-service.ru"],
        addresses=["Казань"], source_names=["yandex_maps"])

    graph = builder.build_from_profiles([p1, p2, p3])
    rels = list(graph.relationships.values())
    # Все три связаны через website → same_as или unknown
    has_links = len(rels) >= 2
    result("Case 3: Multi-city franchise", has_links,
           f"{len(rels)} relationships (expect ≥2)")
    return has_links


# ── Case 4: Rebranding ───────────────────────────────────────────────────

def test_case_4_rebranding():
    """
    Компания сменила название: «Старый Сервис» → «Новый Сервис».
    Один телефон, один сайт → одна Entity.
    """
    p1 = SellerProfile(id="s9", name="Старый Сервис",
        phones=["+7 (495) 555-55-55"], websites=["servis.ru"],
        source_names=["yandex_maps"])
    p2 = SellerProfile(id="s10", name="Новый Сервис",
        phones=["+7 (495) 555-55-55"], websites=["servis.ru"],
        source_names=["company_website"])

    graph = builder.build_from_profiles([p1, p2])
    rels = list(graph.relationships.values())
    linked = len(rels) >= 1
    result("Case 4: Rebranding", linked,
           f"{len(rels)} relationships (expect ≥1)")
    return linked


# ── Case 5: Golden Dataset Positive (Stirkom + Liebherr) ──────────────────

def test_case_5_golden_positive():
    """
    Стирком.ру + Либхерр — перекрёстная проверка.
    Не должны быть связаны.
    """
    p1 = SellerProfile(id="s11", name="Стирком.ру",
        phones=["+7 (915) 338-18-07"], websites=["stirkom.ru"],
        addresses=["Жуковский"], source_names=["yandex_maps", "company_website"])
    p2 = SellerProfile(id="s12", name="Либхерр Сервис",
        phones=["+7 495 797 12 17"], websites=["liebherr-service.ru"],
        addresses=["Москва"], source_names=["yandex_maps", "company_website"])

    graph = builder.build_from_profiles([p1, p2])
    rels = [r for r in graph.relationships.values() if r.type == "same_as"]
    no_false_merge = len(rels) == 0
    result("Case 5: Stirkom vs Liebherr", no_false_merge,
           f"{len(rels)} same_as (expect 0)")
    return no_false_merge


# ── Case 6: Store on 3 Marketplaces ──────────────────────────────────────

def test_case_6_store_3_marketplaces():
    """
    Магазин «Ромашка» на 3 площадках. Один телефон.
    """
    p1 = SellerProfile(id="s13", name="Ромашка Official (YM)",
        phones=["+7 (495) 777-77-77"], source_names=["yandex_market"])
    p2 = SellerProfile(id="s14", name="Romashka Store (WB)",
        phones=["+7 (495) 777-77-77"], source_names=["wildberries"])
    p3 = SellerProfile(id="s15", name="Tech-Romashka (Ozon)",
        phones=["+7 (495) 777-77-77"], source_names=["ozon"])

    graph = builder.build_from_profiles([p1, p2, p3])
    rels = list(graph.relationships.values())
    has_links = len(rels) >= 2
    result("Case 6: Store on 3 marketplaces", has_links,
           f"{len(rels)} relationships (expect ≥2)")
    return has_links


# ── Case 7: Same Phone, Different Names (resellers) ──────────────────────

def test_case_7_reseller():
    """
    Перекуп: один телефон, 3 разных имени.
    Это один человек — должен быть связан.
    """
    p1 = SellerProfile(id="s16", name="Иван", phones=["+7 (999) 111-11-11"],
        source_names=["avito"])
    p2 = SellerProfile(id="s17", name="Сергей (техника)", phones=["+7 (999) 111-11-11"],
        source_names=["avito"])
    p3 = SellerProfile(id="s18", name="Дмитрий", phones=["+7 (999) 111-11-11"],
        source_names=["avito"])

    graph = builder.build_from_profiles([p1, p2, p3])
    rels = list(graph.relationships.values())
    has_links = len(rels) >= 2
    result("Case 7: Reseller same phone", has_links,
           f"{len(rels)} relationships (expect ≥2)")
    return has_links


# ── Case 8: Different Phones, Same Brand, Same City ──────────────────────

def test_case_8_same_brand_same_city():
    """
    Два мастера «Ремонт Bosch» в Москве, разные телефоны.
    Не должны быть объединены.
    """
    p1 = SellerProfile(id="s19", name="Ремонт Bosch",
        phones=["+7 (999) 111-11-11"], addresses=["Москва"],
        source_names=["avito"])
    p2 = SellerProfile(id="s20", name="Ремонт Bosch",
        phones=["+7 (999) 222-22-22"], addresses=["Москва"],
        source_names=["avito"])

    graph = builder.build_from_profiles([p1, p2])
    rels = [r for r in graph.relationships.values() if r.type == "same_as"]
    no_false_merge = len(rels) == 0
    result("Case 8: Same brand, same city", no_false_merge,
           f"{len(rels)} same_as (expect 0)")
    return no_false_merge


# ── Case 9: Empty Profiles (×3) ──────────────────────────────────────────

def test_case_9_empty_profiles():
    """
    Три пустых профиля. Никто не должен быть связан.
    """
    profiles = [
        SellerProfile(id=f"s_empty_{i}", name="",
            source_names=["avito"])
        for i in range(3)
    ]

    graph = builder.build_from_profiles(profiles)
    rels = list(graph.relationships.values())
    no_links = len(rels) == 0
    result("Case 9: Empty profiles (×3)", no_links,
           f"{len(rels)} relationships (expect 0)")
    return no_links


# ── Case 10: Private Master → Company ────────────────────────────────────

def test_case_10_private_to_company():
    """
    Частный мастер стал ИП/ООО.
    Старый телефон + новый сайт → одна Entity.
    """
    p1 = SellerProfile(id="s_old", name="Сергей мастер",
        phones=["+7 (999) 333-33-33"], source_names=["avito"])
    p2 = SellerProfile(id="s_new", name="ИП Сергеев",
        phones=["+7 (999) 333-33-33"], websites=["sergeev-service.ru"],
        inn="123456789012", source_names=["company_website"])

    graph = builder.build_from_profiles([p1, p2])
    rels = list(graph.relationships.values())
    linked = len(rels) >= 1
    result("Case 10: Master → Company", linked,
           f"{len(rels)} relationships (expect ≥1)")
    return linked


# ── Run All ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Milestone 2.5: Graph Stress Test ===\n")

    cases = [
        ("One Seller, Multiple Storefronts", test_case_1_multi_storefront),
        ("Same Brand, Different Sellers", test_case_2_same_brand_diff_sellers),
        ("Multi-city Franchise", test_case_3_franchise),
        ("Rebranding", test_case_4_rebranding),
        ("Golden Dataset: Stirkom vs Liebherr", test_case_5_golden_positive),
        ("Store on 3 Marketplaces", test_case_6_store_3_marketplaces),
        ("Reseller — Same Phone, Diff Names", test_case_7_reseller),
        ("Different Phones, Same Brand, Same City", test_case_8_same_brand_same_city),
        ("Empty Profiles (×3)", test_case_9_empty_profiles),
        ("Private Master → Company", test_case_10_private_to_company),
    ]

    passed = 0
    for name, fn in cases:
        if fn():
            passed += 1

    print(f"\n🎯 {passed}/{len(cases)} кейсов пройдено")
    print()
    if passed == len(cases):
        print("🟢 Graph готов к Ozon/Wildberries. Stress test PASS.")
    else:
        print(f"🟡 {len(cases) - passed} кейсов требуют доработки.")
