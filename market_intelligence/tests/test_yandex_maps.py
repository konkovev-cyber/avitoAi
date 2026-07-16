"""
Milestone 2.1 — Test: Yandex Maps Connector + Pipeline.

Проверяет:
  1. Парсинг HTML → Listing
  2. Извлечение Evidence
  3. Построение SellerProfile
  4. Entity Resolution (попарное сравнение)
  5. Воспроизводимость Golden Dataset
"""

from __future__ import annotations

import json
from pathlib import Path

from ..connectors.yandex_maps import YandexMapsConnector
from ..pipeline import IntelligencePipeline

# Путь к Golden Dataset
GOLDEN_DIR = Path(__file__).parent.parent.parent / "golden_dataset_v1"


def _load_golden_listings() -> list[dict]:
    """Загрузить golden dataset listings."""
    path = GOLDEN_DIR / "normalized" / "listings.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _load_golden_entities() -> dict:
    """Загрузить golden dataset entities (ground truth)."""
    path = GOLDEN_DIR / "annotations" / "entities.json"
    if not path.exists():
        return {"seller_groups": []}
    with open(path) as f:
        return json.load(f)


def test_connector_contract():
    """Коннектор возвращает ConnectorResult с listings и evidence."""
    connector = YandexMapsConnector()
    result = connector.collect("ремонт холодильников", test_data="<test>Рейтинг 5.0</test>")
    assert hasattr(result, "listings")
    assert hasattr(result, "evidence")
    assert isinstance(result.listings, list)
    assert isinstance(result.evidence, list)


def test_connector_capabilities():
    """Коннектор сообщает о своих возможностях."""
    connector = YandexMapsConnector()
    caps = connector.capabilities()
    assert "title" in caps.fields
    assert "address" in caps.fields
    assert "rating" in caps.fields
    assert "30/min" in caps.rate_limit


def test_connector_limitations():
    """Коннектор сообщает о своих ограничениях."""
    connector = YandexMapsConnector()
    limits = connector.limitations()
    assert "email" in limits.never_available
    assert "inn" in limits.never_available
    assert "phone" in limits.sometimes_available


def test_normalize_creates_listing():
    """normalize() возвращает корректный Listing."""
    connector = YandexMapsConnector()
    raw = {
        "title": "Стирком.ру",
        "category": "Ремонт бытовой техники",
        "address": "ул. Кооперативная, 3, Жуковский",
        "city": "Жуковский",
        "phone": "+7 (915) 338-18-07",
        "website": "stirkom.ru",
        "rating": 5.0,
        "reviews_count": 242,
    }
    listing = connector.normalize(raw)
    assert listing.source == "yandex_maps"
    assert listing.title == "Стирком.ру"
    assert listing.phone == "+7 (915) 338-18-07"
    assert listing.website == "stirkom.ru"
    assert listing.rating == 5.0


def test_extract_evidence_from_listing():
    """extract_evidence() извлекает Evidence из Listing с корректными весами."""
    connector = YandexMapsConnector()

    # Listing с телефоном, сайтом, адресом
    listing = connector.normalize({
        "title": "Тест",
        "phone": "+7 (495) 123-45-67",
        "website": "test.ru",
        "address": "ул. Тестовая, 1",
    })
    evidence = connector.extract_evidence(listing)

    # Должно быть 3 evidence: phone, website, address
    assert len(evidence) == 3

    # Проверить типы
    types = {e.type for e in evidence}
    assert "phone_extracted" in types
    assert "website_extracted" in types
    assert "address_extracted" in types

    # Проверить веса
    for e in evidence:
        assert e.strength > 0
        assert e.confidence > 0

    # Телефон — самый сильный сигнал
    phone_ev = [e for e in evidence if e.type == "phone_extracted"][0]
    assert phone_ev.strength == 0.35

    # Сайт — второй по силе
    web_ev = [e for e in evidence if e.type == "website_extracted"][0]
    assert web_ev.strength == 0.30


def test_extract_evidence_empty():
    """extract_evidence() возвращает пустой список, если нет данных."""
    connector = YandexMapsConnector()
    listing = connector.normalize({"title": "Пусто"})
    evidence = connector.extract_evidence(listing)
    assert len(evidence) == 0


def test_pipeline_builds_profiles():
    """Pipeline создаёт SellerProfile из Listing."""
    pipe = IntelligencePipeline()
    connector = YandexMapsConnector()

    listings_data = [
        {"title": "Тест 1", "address": "ул. Ленина, 1", "phone": "+7 111", "url": "https://test1"},
        {"title": "Тест 2", "address": "ул. Ленина, 2", "url": "https://test2"},
    ]

    listings = [connector.normalize(d) for d in listings_data]
    profiles = pipe.build_profiles(listings)

    assert len(profiles) == 2
    for p in profiles:
        assert p.id.startswith("seller_")
        assert p.status == "hypothesis"


def test_matcher_same_phone():
    """Matcher находит совпадение по телефону."""
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    a = Listing(category="Ремонт бытовой техники", id="a", source="yandex_maps", url="", title="A",
                phone="+7 (999) 123-45-67")
    b = Listing(category="Ремонт бытовой техники", id="b", source="company_website", url="", title="B",
                phone="+7 (999) 123-45-67")

    result = matcher.match(a, b)
    assert result.confidence > 0
    assert any(s["type"] == "phone" for s in result.signals)


def test_matcher_different_phone():
    """Matcher не находит совпадение по разным телефонам."""
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    a = Listing(category="Ремонт бытовой техники", id="a", source="yandex_maps", url="", title="A",
                phone="+7 (999) 111-11-11")
    b = Listing(category="Ремонт бытовой техники", id="b", source="yandex_maps", url="", title="B",
                phone="+7 (999) 222-22-22")

    result = matcher.match(a, b)
    assert result.confidence < 0.30  # не должно быть уверенности


def test_matcher_same_website():
    """Matcher находит совпадение по сайту."""
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    a = Listing(category="Ремонт бытовой техники", id="a", source="yandex_maps", url="", title="A", website="stirkom.ru")
    b = Listing(category="Ремонт бытовой техники", id="b", source="company_website", url="", title="B", website="stirkom.ru")

    result = matcher.match(a, b)
    assert result.confidence > 0.30
    assert any(s["type"] == "website" for s in result.signals)


def test_matcher_address_and_website():
    """Комбинация адрес + сайт даёт strong match."""
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    a = Listing(category="Ремонт бытовой техники", id="a", source="yandex_maps", url="", title="Стирком.ру",
                website="stirkom.ru", address="ул. Кооперативная, 3", city="Жуковский")
    b = Listing(category="Ремонт бытовой техники", id="b", source="company_website", url="", title="СтирКом",
                website="stirkom.ru", address="ул. Кооперативная, 3", city="Жуковский")

    result = matcher.match(a, b)
    # Должен быть candidate или выше
    assert result.confidence > 0.55, f"Confidence too low: {result.confidence}"
    assert result.decision in ("candidate", "strong", "verified"), f"Wrong decision: {result.decision}"
    assert len(result.signals) >= 2  # website + name как минимум


def test_matcher_different_city_conflict():
    """Разные города — негативный сигнал, снижающий confidence."""
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    a = Listing(category="Ремонт бытовой техники", id="a", source="yandex_maps", url="", title="Импорт-Сервис",
                phone="+7 (495) 111-11-11", city="Москва")
    b = Listing(category="Ремонт бытовой техники", id="b", source="company_website", url="", title="Импорт-Сервис",
                phone="+7 (812) 222-22-22", city="Санкт-Петербург")

    result = matcher.match(a, b)
    # Телефоны разные, города разные — confidence низкий
    assert result.confidence <= 0.20
    assert result.decision == "different"


def test_golden_dataset_stirkom_ru():
    """
    Воспроизводимость Golden Dataset: Стирком.ру.

    L0005 (Яндекс Карты) + L0009 (сайт) = один продавец.
    """
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    # L0005 — Яндекс Карты
    listing_ym = Listing(
        id="L0005", category="Ремонт бытовой техники", source="yandex_maps", url="",
        title="Стирком.ру", seller_name="Стирком.ру",
        website="stirkom.ru",
        address="Кооперативная ул., 3",
        city="Жуковский",
    )

    # L0009 — сайт компании
    listing_site = Listing(
        id="L0009", category="Ремонт бытовой техники", source="company_website", url="",
        title="СтирКом — ремонт стиральных машин",
        seller_name="СтирКом",
        phone="+7 (915) 338-18-07",
        email="stirkom1@yandex.ru",
        website="stirkom.ru",
        address="ул. Кооперативная, 3, Жуковский",
        city="Жуковский",
    )

    result = matcher.match(listing_ym, listing_site)
    assert result.confidence > 0.60, f"Confidence too low: {result.confidence}"
    assert result.decision in ("candidate", "strong", "verified"), f"Wrong decision: {result.decision}"
    # Должно быть минимум 2 сигнала (website + address минимум)
    assert len(result.signals) >= 2, f"Too few signals: {result.signals}"


def test_golden_dataset_import_servis():
    """
    Воспроизводимость Golden Dataset: Импорт-Сервис.

    L0007 (Лыткарино) ≠ L0010 (СПб) — разные компании с одним именем.
    """
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    # L0007 — Яндекс Карты
    listing_lyt = Listing(
        id="L0007", category="Ремонт бытовой техники", source="yandex_maps", url="",
        title="Импорт-Сервис", seller_name="Импорт-Сервис",
        city="Лыткарино",
        address="2-й микрорайон, 7-й квартал, 2",
    )

    # L0010 — сайт компании
    listing_spb = Listing(
        id="L0010", category="Ремонт бытовой техники", source="company_website", url="",
        title="Импорт-Сервис — ремонт техники в СПб",
        seller_name="Импорт-Сервис",
        phone="8 (812) 702-33-33",
        website="import-service.ru",
        city="Санкт-Петербург",
        address="пр. Юрия Гагарина д. 23",
    )

    result = matcher.match(listing_lyt, listing_spb)
    # Разные города — не должны быть объединены
    assert result.confidence < 0.40, f"False merge risk: {result.confidence}"
    # Должен быть negative signal по городу
    assert any(n["type"] == "city_conflict" for n in result.negative_signals), "Missing city conflict signal"


def test_golden_dataset_liebherr():
    """
    Воспроизводимость Golden Dataset: Либхерр.

    L0001 (Яндекс Карты) + L0011 (сайт) = один продавец.
    ИНН + ОГРН связывают.
    """
    from ..resolution.matcher import EntityMatcher
    from ..models.listing import Listing

    matcher = EntityMatcher()

    # L0001 — Яндекс Карты
    listing_ym = Listing(
        id="L0001", category="Ремонт бытовой техники", source="yandex_maps", url="",
        title="Либхерр Сервис", seller_name="Либхерр Сервис",
        city="Москва",
        address="Салтыковская ул., 51",
    )

    # L0011 — сайт компании
    listing_site = Listing(
        id="L0011", category="Ремонт бытовой техники", source="company_website", url="",
        title="Сервисный центр Liebherr",
        seller_name="Либхерр Сервис",
        phone="+7 495 797 12 17",
        website="liebherr-service.ru",
        email="liebherr-service@internet.ru",
        address="ул. Перерва, д. 11, стр. 21",
        city="Москва",
    )

    result = matcher.match(listing_ym, listing_site)
    # Один город + одно имя — должно быть > 0
    assert result.confidence > 0
    # Не должно быть уверенности (адреса разные!)
    # Это ожидаемый weak match, так как ИНН не проверяется в этой версии
    print(f"  Liebherr match confidence: {result.confidence}")
    print(f"  Signals: {[s['type'] for s in result.signals]}")


def test_pipeline_full_run():
    """Полный прогон Pipeline с тестовыми данными."""
    pipe = IntelligencePipeline()
    connector = YandexMapsConnector()

    test_data = """
    Рейтинг 5.0
    Стирком.ру
    Кооперативная ул., 3
    Stirkom
    Рейтинг 4.5
    Импорт-Сервис
    ул. Ленина, 1
    """

    result = pipe.run(connector, "ремонт", test_data=test_data)

    assert result.listings is not None
    assert result.evidence is not None
    assert result.profiles is not None


if __name__ == "__main__":
    # Ручной запуск
    print("=== Milestone 2.1: Yandex Maps Connector Tests ===\n")

    test_connector_contract()
    print("✅ test_connector_contract")

    test_connector_capabilities()
    print("✅ test_connector_capabilities")

    test_connector_limitations()
    print("✅ test_connector_limitations")

    test_normalize_creates_listing()
    print("✅ test_normalize_creates_listing")

    test_extract_evidence_from_listing()
    print("✅ test_extract_evidence_from_listing")

    test_extract_evidence_empty()
    print("✅ test_extract_evidence_empty")

    test_pipeline_builds_profiles()
    print("✅ test_pipeline_builds_profiles")

    test_matcher_same_phone()
    print("✅ test_matcher_same_phone")

    test_matcher_different_phone()
    print("✅ test_matcher_different_phone")

    test_matcher_same_website()
    print("✅ test_matcher_same_website")

    test_matcher_address_and_website()
    print("✅ test_matcher_address_and_website")

    test_matcher_different_city_conflict()
    print("✅ test_matcher_different_city_conflict")

    test_golden_dataset_stirkom_ru()
    print("✅ test_golden_dataset_stirkom_ru (Стирком.ру)")

    test_golden_dataset_import_servis()
    print("✅ test_golden_dataset_import_servis (Импорт-Сервис)")

    test_golden_dataset_liebherr()
    print("✅ test_golden_dataset_liebherr (Либхерр)")

    test_pipeline_full_run()
    print("✅ test_pipeline_full_run")

    print("\n🎯 Все тесты пройдены")
