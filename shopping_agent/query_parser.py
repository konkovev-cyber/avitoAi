"""Query Parser — разбор пользовательского запроса в структурированный поиск."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ProductQuery:
    """Структурированный запрос пользователя."""
    brand: str = ""
    model: str = ""
    memory: str = ""
    condition: str = "любой"  # новый | б/у | любой
    budget: int = 0
    city: str = ""
    raw: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.brand or self.model)

    @property
    def needs_clarification(self) -> bool:
        return not self.model

    def summary(self) -> str:
        parts = []
        if self.model and self.brand and self.model.lower().startswith(self.brand.lower()):
            parts.append(self.model)
        else:
            if self.brand:
                parts.append(self.brand)
            if self.model:
                parts.append(self.model)
        if self.memory:
            parts.append(self.memory)
        if self.budget:
            parts.append(f"до {self.budget:,}₽".replace(",", " "))
        if self.condition != "любой":
            parts.append(f"({self.condition})")
        return " ".join(parts) or self.raw


# ── Brand/Model Database ──────────────────────────────────────────────────

BRANDS = {
    "apple": "Apple", "iphone": "Apple iPhone", "айфон": "Apple iPhone",
    "samsung": "Samsung", "galaxy": "Samsung Galaxy",
    "xiaomi": "Xiaomi", "сяоми": "Xiaomi",
    "macbook": "Apple MacBook", "макбук": "Apple MacBook",
    "airpods": "Apple AirPods", "эйрподс": "Apple AirPods",
    "ps5": "Sony PlayStation 5", "playstation": "Sony PlayStation 5",
    "playstation 5": "Sony PlayStation 5", "пятачок": "Sony PlayStation 5",
    "nintendo": "Nintendo Switch", "нинтендо": "Nintendo Switch",
    "dyson": "Dyson", "дайсон": "Dyson",
    "roborock": "Roborock", "роборок": "Roborock",
    "dyson v15": "Dyson V15",
    "iphone 15 pro": "Apple iPhone 15 Pro",
    "iphone 14 pro": "Apple iPhone 14 Pro",
    "iphone 15": "Apple iPhone 15",
    "iphone 14": "Apple iPhone 14",
    "iphone 13": "Apple iPhone 13",
    "iphone 12": "Apple iPhone 12",
    "macbook air": "Apple MacBook Air",
    "macbook pro": "Apple MacBook Pro",
    "airpods pro": "Apple AirPods Pro",
    "ps5 slim": "Sony PlayStation 5 Slim",
}

CONDITIONS = {
    "новый": "новый", "new": "новый", "б/у": "б/у", "б/у ": "б/у",
    "подержанный": "б/у", "бывший": "б/у", "used": "б/у",
    "восстановленный": "восстановленный", "refurbished": "восстановленный",
}

MEMORY_PATTERN = re.compile(r"(\d+)\s*(gb|гб|tb|тб)", re.IGNORECASE)
BUDGET_PATTERN = re.compile(r"(?:до|менее|дешевле|budget)\s*[:\s]*(\d[\d\s]*\d)\s*₽?", re.IGNORECASE)
BUDGET_PATTERN2 = re.compile(r"(\d[\d\s]*\d)\s*₽")
BUDGET_PATTERN3 = re.compile(r"(\d[\d\s]*\d)\s*(?:р|руб|рублей)")


def parse_query(text: str) -> ProductQuery:
    """Разобрать текстовый запрос в ProductQuery."""
    q = ProductQuery(raw=text)
    low = text.lower().strip()

    # Budget
    for pattern in [BUDGET_PATTERN, BUDGET_PATTERN2, BUDGET_PATTERN3]:
        m = pattern.search(text)
        if m:
            num = int(m.group(1).replace(" ", "").replace("\xa0", ""))
            if 1000 <= num <= 10_000_000:
                q.budget = num
                break

    # Memory
    m = MEMORY_PATTERN.search(text)
    if m:
        size = m.group(1)
        unit = m.group(2).upper().replace("Г", "G").replace("Т", "T")
        q.memory = f"{size}GB" if "G" in unit else f"{size}TB"

    # Condition
    for key, val in CONDITIONS.items():
        if key in low:
            q.condition = val
            break

    # Brand/Model — longest match first
    matched = False
    for pattern, full_name in sorted(BRANDS.items(), key=lambda x: -len(x[0])):
        if pattern in low:
            parts = full_name.split(" ", 1)
            q.brand = parts[0]
            q.model = full_name
            matched = True
            break

    # iPhone specific model extraction
    if not matched:
        m = re.search(r"(?:iphone|айфон)\s*(\d+)\s*(pro|max|plus|mini)?", low)
        if m:
            num = m.group(1)
            suffix = (m.group(2) or "").title()
            q.brand = "Apple"
            q.model = f"iPhone {num} {suffix}".strip()

    # MacBook specific
    if not matched:
        m = re.search(r"(?:macbook|макбук)\s*(air|pro)?\s*(m\d+)?", low)
        if m:
            line = (m.group(1) or "").title()
            chip = (m.group(2) or "").upper()
            q.brand = "Apple"
            q.model = f"MacBook {line} {chip}".strip()

    # PS5
    if not matched:
        if any(w in low for w in ["ps5", "playstation 5", "пятачок"]):
            q.brand = "Sony"
            q.model = "PlayStation 5"
            if "slim" in low:
                q.model = "PlayStation 5 Slim"

    return q
