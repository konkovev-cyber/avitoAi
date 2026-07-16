"""Search Expander — расширение запроса для максимального покрытия источников."""

from __future__ import annotations

from .query_parser import ProductQuery


# ── Synonym Database ──────────────────────────────────────────────────────

SYNONYMS = {
    "apple iphone 15 pro": [
        "iPhone 15 Pro", "iPhone15Pro", "Apple iPhone 15 Pro",
        "Айфон 15 Про", "iPhone 15Pro", "Apple iPhone15Pro",
    ],
    "apple iphone 15": [
        "iPhone 15", "iPhone15", "Apple iPhone 15",
        "Айфон 15", "iPhone 15 128gb", "iPhone 15 256gb",
    ],
    "apple iphone 14 pro": [
        "iPhone 14 Pro", "iPhone14Pro", "Apple iPhone 14 Pro",
        "Айфон 14 Про",
    ],
    "apple iphone 14": [
        "iPhone 14", "iPhone14", "Apple iPhone 14",
        "Айфон 14",
    ],
    "apple iphone 13": [
        "iPhone 13", "iPhone13", "Apple iPhone 13",
        "Айфон 13",
    ],
    "apple macbook air": [
        "MacBook Air", "MacBookAir", "Apple MacBook Air",
        "Макбук Аир", "MacBook Air M1", "MacBook Air M2", "MacBook Air M3",
    ],
    "apple macbook pro": [
        "MacBook Pro", "MacBookPro", "Apple MacBook Pro",
        "Макбук Про",
    ],
    "sony playstation 5": [
        "PS5", "PlayStation 5", "PlayStation5", "Sony PS5",
        "Пристав PlayStation 5", "PS 5",
    ],
    "sony playstation 5 slim": [
        "PS5 Slim", "PlayStation 5 Slim", "PS5Slim", "Sony PS5 Slim",
    ],
    "apple airpods pro": [
        "AirPods Pro", "AirPodsPro", "Apple AirPods Pro",
        "Эйрподс Про", "AirPods Pro 2",
    ],
    "dyson v15": [
        "Dyson V15", "DysonV15", "Dyson V15 Detect",
        "Дайсон V15", "Dyson v15",
    ],
}

BRAND_SYNONYMS = {
    "Apple": ["apple", "эппл", "эпл"],
    "Samsung": ["samsung", "самсунг"],
    "Xiaomi": ["xiaomi", "сяоми", "ми"],
    "Sony": ["sony", "сони"],
    "Dyson": ["dyson", "дайсон"],
}


def expand_search(query: ProductQuery) -> list[str]:
    """Расширить запрос в список поисковых фраз."""
    results = []

    # 1. Exact model from synonym DB
    key = query.model.lower() if query.model else ""
    for syn_key, syns in SYNONYMS.items():
        if syn_key in key or key in syn_key:
            results.extend(syns)

    # 2. Model + memory combination
    if query.model and query.memory:
        results.append(f"{query.model} {query.memory}")
        results.append(f"{query.model} {query.memory.replace('GB', ' гб')}")

    # 3. Raw model
    if query.model:
        results.append(query.model)

    # 4. Brand + keywords
    if query.brand:
        brand_syns = BRAND_SYNONYMS.get(query.brand, [query.brand.lower()])
        for syn in brand_syns:
            if query.model:
                model_part = query.model.replace(query.brand, "").strip()
                results.append(f"{syn} {model_part}".strip())

    # 5. Raw text as fallback
    if query.raw and query.raw not in results:
        # Extract just product-related words
        words = query.raw.split()
        budget_words = {"до", "менее", "дешевле", "бюджет", "₽", "р", "руб"}
        product_words = [w for w in words if w.lower() not in budget_words and not w.isdigit()]
        if product_words:
            results.append(" ".join(product_words))

    # Deduplicate, preserve order
    seen = set()
    unique = []
    for r in results:
        r_clean = r.strip().lower()
        if r_clean and r_clean not in seen:
            seen.add(r_clean)
            unique.append(r.strip())

    return unique[:10]  # Max 10 search variants


def format_search_plan(query: ProductQuery, variants: list[str]) -> str:
    """Человекочитаемый план поиска."""
    lines = [
        f"🔍 Ищу: {query.summary()}",
        "",
        "Ищу по источникам:",
        "  ✓ Avito",
        "  ✓ Яндекс Маркет",
        "  ✓ Ozon",
        "  ✓ Wildberries",
        "  ✓ Яндекс Карты",
        "",
        f"Поисковых запросов: {len(variants)}",
    ]
    if variants[:3]:
        lines.append(f"Примеры: {', '.join(variants[:3])}")
    return "\n".join(lines)
