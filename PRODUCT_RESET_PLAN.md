# Product Reset Plan — Shopping Intelligence Agent

> *Переход от B2B Market Intelligence к Consumer Shopping Agent*

---

## 1. Что сохраняем из текущего проекта

| Компонент | Статус | Использование |
|-----------|--------|---------------|
| **Connectors** (6) | ✅ KEEP | Поиск товаров по источникам |
| **Evidence Layer** | ✅ KEEP | Проверка продавцов, данных |
| **Entity Resolution** | ✅ KEEP | Объединение одинаковых товаров/продавцов |
| **Market Graph** | ✅ KEEP | Связи продавцов, товаров, цен |
| **Monitoring (MarketDiff)** | ✅ KEEP | Отслеживание изменений цен |
| **144 теста** | ✅ KEEP | Регрессия ядра |
| **Rule Registry v2** | ⚠️ ADAPT | Только для trust/price scoring |
| **Lead Generation** | ❌ DEPRECATE | B2B лиды больше не нужны |
| **Opportunity Engine** | ❌ DEPRECATE | B2B возможности больше не нужны |
| **Market Map HTML** | ❌ DEPRECATE | B2B визуализация |
| **Customer Workflow** | ❌ DEPRECATE | B2B сценарии |

---

## 2. Что отключаем

```yaml
deprecated_modules:
  - intelligence/opportunity.py    (B2B opportunity signals)
  - intelligence/scorer.py         (B2B seller visibility)
  - intelligence/report.py         (B2B market report)
  - intelligence/commercial/       (B2B leads + scoring)
  - map/html_map.py                (B2B market map)
  - customer_workflow/             (B2B reports)
  - phase6_external_user/          (B2B validation)
  - customer_demo/                 (B2B demo)
  - pilot_dataset_v1/              (B2B pilot data — archive)
  - phase6_phone_repair/           (B2B niche data — archive)
```

**НЕ удаляем** — просто не используем. Могут вернуться.

---

## 3. Новые модули

```yaml
new_modules:
  shopping_agent/
    ├── query_parser.py       — "iPhone 15 Pro до 80000" → structured query
    ├── search_expander.py    — синонимы, бренды, модели, опечатки
    ├── price_intelligence.py — средняя цена, экономия, рыночный диапазон
    ├── trust_scorer.py       — 0-100 доверие к продавцу
    ├── recommendation.py     — лучшие варианты + объяснение
    ├── deal_finder.py        — объединение всех шагов
    └── tests/
```

---

## 4. Новый Telegram Bot UX

### Старый (B2B)

```
/start → бизнес → ниша → отчёт
```

### Новый (Consumer)

```
/start
→ "Что ищем?"
→ "iPhone 15 Pro 256GB до 80000"
→ бот уточняет (если нужно)
→ "Ищу по 6 источникам..."
→ 🔥 Результат:
   1. iPhone 15 Pro 256GB — 74 900₽ (средняя 89 000₽, экономия 14 100₽)
      Продавец: доверие 87/100, Avito
   2. iPhone 15 Pro 256GB — 78 000₽ (средняя 89 000₽, экономия 11 000₽)
      Продавец: доверие 72/100, Яндекс Маркет
   ...
→ "Полезно?" [✅ Да] [❌ Нет]
```

---

## 5. MVP за 7 дней

| День | Задача |
|------|--------|
| 1 | Аудит ядра, PRODUCT_RESET_PLAN.md, новая структура |
| 2 | query_parser.py + search_expander.py |
| 3 | price_intelligence.py |
| 4 | trust_scorer.py |
| 5 | deal_finder.py + recommendation.py |
| 6 | Telegram Bot UX rewrite |
| 7 | Тест на 20 запросах (iPhone, MacBook, PS5) |

---

## 6. Что НЕ делаем

```yaml
forbidden:
  - "новые коннекторы"
  - "новые архитектурные слои"
  - "AI/ML модели"
  - "SaaS платформу"
  - "платежную систему"
  - "рекламу"
  - "B2B отчёты"
  - "маркетплейс-интеграции через API"
```

---

## 7. MVP Цель

```yaml
goal: "Пользователь написал 'iPhone 15 Pro' и получил 5 вариантов дешевле рынка"
success_metric: "Пользователь сказал 'О, это дешевле чем я находил'"
anti_success: "Пользователь сказал 'Я уже это видел на Авито'"
```

---

## 8. Целевой сценарий

```
Пользователь:
"Найди iPhone 15 Pro 256GB до 80000₽"

Бот парсит:
  product: iPhone 15 Pro
  memory: 256GB
  budget: 80000
  condition: новый (по умолчанию)

Ищет:
  Avito: 12 предложений
  Яндекс Маркет: 8
  Ozon: 3
  WB: 5
  Сайты: 4

Фильтрует:
  price <= 80000: 15
  trusted sellers: 8

Сортирует по цене + доверию.

Ответ:
  🔥 Лучшие варианты (3 из 8):
  1. 74 900₽ — доверие 87 — Avito — seller verified
  2. 76 500₽ — доверие 82 — Яндекс Маркет
  3. 79 000₽ — доверие 75 — Ozon

  Экономия до 14 100₽ от средней цены.
```

---

*Shopping Intelligence Agent · Product Reset v1*
