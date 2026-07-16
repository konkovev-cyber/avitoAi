"""
Milestone 2.2 — Tests: Avito Connector + Cross-Source Resolution.

Проверяет:
  1. Парсинг Avito → Listing
  2. Evidence extraction из грязных данных
  3. Cross-source matching с Yandex Maps
  4. Positive Match
  5. False Merge protection
  6. Sparse Data (Unknown)
"""

from ..connectors.avito import AvitoConnector
from ..models.listing import Listing
from ..models.evidence import Evidence
from ..resolution.matcher import EntityMatcher


# ── Test Data Fixtures ────────────────────────────────────────────────────

AVITO_LISTING_WITH_PHONE = {
    "url": "https://avito.ru/moskva/remont-holodilnikov-123",
    "title": "Ремонт холодильников на дому",
    "category": "Ремонт бытовой техники / Ремонт холодильников",
    "description": "Ремонтирую холодильники любых марок. Выезд по Москве. Звоните Сергею +7 (999) 123-45-67",
    "seller_name": "Сергей",
    "price": 1500,
    "city": "Москва",
    "address": "ул. Ленина, 10",
    "phone": "+7 (999) 123-45-67",
}

AVITO_LISTING_ANOTHER_PHONE = {
    "url": "https://avito.ru/moskva/remont-stiralok-456",
    "title": "Ремонт стиральных машин",
    "category": "Ремонт бытовой техники / Ремонт стиральных машин",
    "description": "Ремонт стиральных машин на дому. Быстро, качественно.",
    "seller_name": "Иван",
    "price": 2000,
    "city": "Москва",
    "phone": "+7 (999) 777-77-77",
    "address": "ул. Ленина, 10",
}

AVITO_NO_CONTACTS = {
    "url": "https://avito.ru/moskva/remont-789",
    "title": "Ремонт любой техники",
    "category": "Ремонт бытовой техники",
    "description": "Делаю ремонт быстро и недорого. Опыт 10 лет.",
    "seller_name": "Мастер",
    "city": "Москва",
}

AVITO_DIFFERENT_CITY = {
    "url": "https://avito.ru/spb/remont-holodilnikov-101",
    "title": "Ремонт холодильников",
    "category": "Ремонт бытовой техники / Ремонт холодильников",
    "description": "Ремонт холодильников в СПб.",
    "seller_name": "Сергей",
    "phone": "+7 (812) 555-55-55",
    "city": "Санкт-Петербург",
}

AVITO_SPARSE = {
    "url": "https://avito.ru/moskva/usluga-999",
    "title": "Ремонт",
    "category": "Ремонт бытовой техники",
    "description": "",
    "seller_name": "",
    "city": "Москва",
}

# Yandex Maps listing for cross-source testing
YM_STIRKOM = {
    "title": "Стирком.ру",
    "category": "Ремонт бытовой техники",
    "address": "ул. Кооперативная, 3, Жуковский",
    "city": "Жуковский",
    "phone": "+7 (915) 338-18-07",
    "website": "stirkom.ru",
}

YM_IMPORT_LYTKARINO = {
    "title": "Импорт-Сервис",
    "category": "Ремонт бытовой техники",
    "address": "2-й микрорайон, 7-й квартал, 2",
    "city": "Лыткарино",
}


# ── Tests ─────────────────────────────────────────────────────────────────

def test_connector_contract():
    """AvitoConnector возвращает ConnectorResult с listings и evidence."""
    connector = AvitoConnector()
    result = connector.collect("ремонт", test_data=[AVITO_LISTING_WITH_PHONE])
    assert len(result.listings) == 1
    assert len(result.evidence) >= 1
    assert result.listings[0].source == "avito"


def test_normalize_with_phone():
    """normalize() сохраняет телефон из Avito."""
    connector = AvitoConnector()
    listing = connector.normalize(AVITO_LISTING_WITH_PHONE)
    assert listing.phone == "+7 (999) 123-45-67"
    assert listing.title == "Ремонт холодильников на дому"
    assert listing.seller_name == "Сергей"
    assert listing.price == 1500


def test_normalize_sparse():
    """normalize() работает с минимальными данными."""
    connector = AvitoConnector()
    listing = connector.normalize(AVITO_SPARSE)
    assert listing.title == "Ремонт"
    assert listing.phone is None
    assert listing.seller_name == ""


def test_extract_evidence_from_phone():
    """Извлекает phone evidence из явного поля."""
    connector = AvitoConnector()
    listing = connector.normalize(AVITO_LISTING_WITH_PHONE)
    evidence = connector.extract_evidence(listing)
    types = [e.type for e in evidence]
    assert "phone_extracted" in types
    # phone evidence должен иметь strength 0.35
    phone_ev = [e for e in evidence if e.type == "phone_extracted"][0]
    assert phone_ev.strength == 0.35


def test_extract_evidence_from_description():
    """Извлекает телефон из описания, если нет явного."""
    connector = AvitoConnector()
    item = dict(AVITO_LISTING_WITH_PHONE)
    item["phone"] = None  # убрали явный телефон
    listing = connector.normalize(item)
    evidence = connector.extract_evidence(listing)
    types = [e.type for e in evidence]
    assert "phone_extracted" in types
    # телефон должен быть извлечён из описания
    phone_ev = [e for e in evidence if e.type == "phone_extracted"][0]
    assert "+7 (999) 123-45-67" in phone_ev.value


def test_extract_evidence_sparse():
    """Из разреженных данных evidence не извлекается."""
    connector = AvitoConnector()
    listing = connector.normalize(AVITO_SPARSE)
    evidence = connector.extract_evidence(listing)
    assert len(evidence) == 0


def test_connector_limitations():
    """Avito не может вернуть email, website, inn."""
    connector = AvitoConnector()
    limits = connector.limitations()
    assert "email" in limits.never_available
    assert "website" in limits.never_available
    assert "inn" in limits.never_available
    assert "phone" in limits.sometimes_available


def test_connector_capabilities():
    """Connector сообщает capabilities."""
    connector = AvitoConnector()
    caps = connector.capabilities()
    assert "title" in caps.fields
    assert "phone" in caps.fields
    assert caps.requires_proxy is True
    assert "5/min" in caps.rate_limit


def test_cross_source_same_phone():
    """
    Positive Match: Avito + Yandex Maps по телефону.

    Один и тот же телефон → один продавец (confidence > 0.30).
    """
    matcher = EntityMatcher()

    avito = Listing(
        id="av_test", category="Ремонт бытовой техники",
        source="avito", url="", title="Ремонт стиральных машин",
        seller_name="СтирКом", phone="+7 (915) 338-18-07",
        city="Жуковский",
    )
    ym = Listing(
        id="ym_test", category="Ремонт бытовой техники",
        source="yandex_maps", url="", title="Стирком.ру",
        seller_name="Стирком.ру", phone="+7 (915) 338-18-07",
        website="stirkom.ru", city="Жуковский",
    )

    result = matcher.match(avito, ym)
    assert result.confidence > 0.30, f"Too low: {result.confidence}"
    assert any(s["type"] == "phone" for s in result.signals), "Phone signal missing"


def test_cross_source_different_phone():
    """
    Negative Match: Avito + Yandex Maps — разные телефоны, один город.

    Должен быть DIFFERENT (confidence ≤ 0.30).
    """
    matcher = EntityMatcher()

    avito = Listing(
        id="av_test1", category="Ремонт бытовой техники",
        source="avito", url="", title="Ремонт холодильников",
        seller_name="Сергей", phone="+7 (999) 111-11-11",
        city="Москва",
    )
    ym = Listing(
        id="ym_test1", category="Ремонт бытовой техники",
        source="yandex_maps", url="", title="Ремонт холодильников",
        seller_name="Сергей", phone="+7 (999) 222-22-22",
        city="Москва",
    )

    result = matcher.match(avito, ym)
    assert result.confidence <= 0.30, f"False merge risk: {result.confidence}"
    assert result.decision == "different", f"Should be different: {result.decision}"


def test_cross_source_same_address_different_name():
    """
    Complex: Avito + Yandex Maps — один адрес, разные имена.

    Адрес совпадает → candidate (но не verified без телефона).
    """
    matcher = EntityMatcher()

    avito = Listing(
        id="av_addr", category="Ремонт бытовой техники",
        source="avito", url="", title="Ремонт стиральных машин",
        seller_name="СтирКом", address="Кооперативная ул., 3",
        city="Жуковский",
    )
    ym = Listing(
        id="ym_addr", category="Ремонт бытовой техники",
        source="yandex_maps", url="", title="Мастер на час",
        seller_name="Стирком.ру", address="Кооперативная ул., 3",
        city="Жуковский", website="stirkom.ru",
    )

    result = matcher.match(avito, ym)
    assert result.confidence > 0.30, f"Address match should raise confidence: {result.confidence}"
    # address + website + city should give > 0.60
    print(f"  Combined: {result.confidence}, signals: {[s['type'] for s in result.signals]}")


def test_sparse_data_unknown():
    """
    Sparse Data: Avito без контактов → confidence должен быть низким.

    Система не должна угадывать.
    """
    matcher = EntityMatcher()

    a = Listing(
        id="av_sparse1", category="Ремонт бытовой техники",
        source="avito", url="", title="Ремонт", seller_name="",
        city="Москва",
    )
    b = Listing(
        id="av_sparse2", category="Ремонт бытовой техники",
        source="avito", url="", title="Услуги", seller_name="",
        city="Москва",
    )

    result = matcher.match(a, b)
    assert result.confidence < 0.40, f"Should be uncertain: {result.confidence}"
    assert result.decision == "different", f"Should be different: {result.decision}"


def test_golden_dataset_stirkom_cross_source():
    """
    Golden Dataset воспроизводимость: Avito → Yandex Maps.

    Стирком.ру: если Avito listing имеет тот же телефон и адрес,
    система должна найти strong match.
    """
    matcher = EntityMatcher()

    # Avito listing (как если бы нашли на Avito)
    avito = Listing(
        id="av_stirkom", category="Ремонт бытовой техники",
        source="avito", url="", title="Ремонт стиральных машин",
        seller_name="СтирКом", phone="+7 (915) 338-18-07",
        address="ул. Кооперативная, 3", city="Жуковский",
    )

    # Yandex Maps (из Golden Dataset L0005)
    ym = Listing(
        id="ym_stirkom", category="Ремонт бытовой техники",
        source="yandex_maps", url="", title="Стирком.ру",
        seller_name="Стирком.ру", phone="+7 (915) 338-18-07",
        website="stirkom.ru",
        address="ул. Кооперативная, 3", city="Жуковский",
    )

    result = matcher.match(avito, ym)
    # phone (0.35) + website (0.35) + address (0.30) + city (0.08) + name (0.064)
    # → capped at ~0.85-1.0
    assert result.confidence > 0.50, f"Cross-source too low: {result.confidence}"
    assert result.decision in ("candidate", "strong", "verified")
    assert len(result.signals) >= 3, f"Expected 3+ signals: {[s['type'] for s in result.signals]}"


def test_avito_full_pipeline():
    """Полный прогон: Avito Connector → Pipeline → Profiles."""
    from ..pipeline import IntelligencePipeline

    pipe = IntelligencePipeline()
    connector = AvitoConnector()

    # 3 тестовых объявления Avito
    test_data = [
        AVITO_LISTING_WITH_PHONE,
        AVITO_LISTING_ANOTHER_PHONE,
        AVITO_NO_CONTACTS,
    ]

    result = pipe.run(connector, "ремонт", test_data=test_data)
    assert len(result.listings) == 3, f"Expected 3 listings: {len(result.listings)}"
    assert len(result.evidence) > 0, "Expected evidence"
    assert len(result.profiles) == 3, "Expected 3 profiles"


if __name__ == "__main__":
    print("=== Milestone 2.2: Avito Connector Tests ===\n")

    tests = [
        test_connector_contract,
        test_normalize_with_phone,
        test_normalize_sparse,
        test_extract_evidence_from_phone,
        test_extract_evidence_from_description,
        test_extract_evidence_sparse,
        test_connector_limitations,
        test_connector_capabilities,
        test_cross_source_same_phone,
        test_cross_source_different_phone,
        test_cross_source_same_address_different_name,
        test_sparse_data_unknown,
        test_golden_dataset_stirkom_cross_source,
        test_avito_full_pipeline,
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
