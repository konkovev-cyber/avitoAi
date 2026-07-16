# Intelligence Model — Market Intelligence OS v1.0

> *Мы моделируем реальный рынок, а не страницы сайтов.*

---

## 1. Core Entities

### 1.1 Source — Источник данных

Источник, из которого получена информация. Определяет происхождение, уровень доверия и метод сбора.

```yaml
Source:
  id: str                          # source_avito, source_youla, source_telegram
  type: enum                       # marketplace | classifieds | retail | social | catalog | direct_site
  name: str                        # "Avito", "Юла", "Ozon"
  trust_level: float               # 0.0–1.0 — насколько доверять данным из этого источника
  connector_version: str           # версия коннектора
  is_official_api: bool            # true = официальное API, false = парсинг
  rate_limit: str                  # "10/min"
```

| Source | Тип | Trust Level | API |
|--------|-----|-------------|-----|
| Avito | classifieds | 0.7 | Нет (парсинг) |
| Юла | marketplace | 0.6 | Неофициальное |
| Ozon | retail | 0.9 | Официальное API |
| Сайт компании | direct_site | 0.5 | Нет |
| Telegram | social | 0.4 | API |

---

### 1.2 Listing — Сырое наблюдение

Listing — это **единичное наблюдение**. Он доказывает, что в конкретный момент на конкретной площадке существовало предложение.

```yaml
Listing:
  id: str
  source: Source
  source_url: str                  # прямая ссылка
  title: str
  description: str
  price: float
  currency: str
  status: enum                     # active | sold | removed | expired
  first_seen: datetime
  last_seen: datetime
  raw_data: dict                   # полный оригинальный ответ источника
  hash: str                        # SHA256 ключевых полей
```

**Важно:** Listing не равен продавцу. Listing — это **свидетельство**, а не сущность.

Правило: Listing никогда не удаляется. Он может быть помечен как `inactive`, `duplicate` или `superseded`, но не удаляется.

---

### 1.3 Evidence — Доказательство

Evidence — атомарная единица доказательства. Любой вывод системы строится на совокупности Evidence.

```yaml
Evidence:
  id: str
  type: enum                       # phone | email | address | photo_hash | text_fingerprint |
                                   # brand | name | site | social | logo | geo | tax_id
  value: str                       # значение признака
  weight: float                    # 0.0–1.0 — вклад в итоговое решение
  source_listing: str              # ID listing, откуда извлечено
  source_field: str                # конкретное поле в listing
  extracted_by: enum               # rule_based | ai | human
  reliability: float               # 0.0–1.0 — насколько можно доверять этому evidence
  timestamp: datetime
  metadata: dict                   # контекст извлечения
```

Примеры:

```yaml
evidence_001:
  type: phone
  value: "+7 (999) 123-45-67"
  weight: 0.35
  source_listing: "listing_avito_123"
  extracted_by: rule_based
  reliability: 0.95  # телефон — один из самых надёжных признаков

evidence_002:
  type: photo_hash
  value: "sha256:a1b2c3d4e5f6..."
  weight: 0.20
  source_listing: "listing_youla_456"
  extracted_by: ai
  reliability: 0.85  # хеш фото — надёжно, но фото может быть украдено
```

---

### 1.4 Seller — Участник рынка (гипотетический)

Seller — это **предполагаемый продавец**. Результат объединения Evidence.

```yaml
Seller:
  id: str
  status: enum                     # hypothesis | candidate | confirmed | verified
  confidence: float                # 0.0–1.0 — насколько уверены, что это реальный продавец
  created_from: list[Evidence]     # какие evidence привели к созданию
  merged_from: list[str]           # ID других seller, которые были объединены в этого
  split_warning: bool              # может ли этот seller быть результатом ложного объединения
  first_seen: datetime
  last_seen: datetime
```

Seller — **единственная сущность, которая может быть ошибочной.** Система должна сохранять возможность разделения и пересмотра.

---

### 1.5 Company — Юридическая/коммерческая сущность

Company — это подтверждённая организация. Отличается от Seller тем, что имеет юридический статус.

```yaml
Company:
  id: str
  name: str
  legal_name: str                  # полное юр. наименование
  tax_id: str                      # ИНН / ОГРН
  linked_sellers: list[Seller]     # продавцы, связанные с компанией
  verified: bool                   # подтверждена через официальные источники
  registration_date: date
  status: enum                     # active | dissolved | unknown
```

Связь Seller → Company не является обязательной. Многие Seller — это физические лица без юрлица.

---

### 1.6 Contact — Способы связи

```yaml
Contact:
  id: str
  type: enum                       # phone | email | website | telegram | whatsapp | vk | instagram
  value: str
  verified: bool
  first_seen: datetime
  last_seen: datetime
  evidence: list[Evidence]         # какие listing'и подтверждают этот контакт
```

Contact — ключевой элемент для связывания Seller. Телефон, повторяющийся в разных объявлениях с разными названиями — сильнейший сигнал.

---

### 1.7 Product / Service — Что продаётся

```yaml
Product:
  id: str
  title: str
  category: str                    # дерево категорий
  brand: str
  model: str
  condition: enum                  # new | likenew | used | broken
  price_range: dict                # min, max, median, avg
  listed_by: list[Seller]          # кто продаёт
  evidence: list[Evidence]
```

---

### 1.8 Location — География

```yaml
Location:
  id: str
  address: str
  city: str
  region: str
  country: str
  coordinates: dict                # lat, lng
  linked_sellers: list[Seller]
```

---

### 1.9 Relationship — Связь между сущностями

```yaml
Relationship:
  id: str
  type: enum                       # same_seller | same_company | same_contact | competitive |
                                   # supplier | partner | franchise
  from_entity: (type, id)          # любая сущность
  to_entity: (type, id)
  confidence: float
  evidence: list[Evidence]
  reasoning: str                   # человекочитаемое объяснение
  created_at: datetime
  reviewed: bool
  expires_at: datetime             # связи могут устаревать
```

---

### 1.10 Market Segment — Категория рынка

```yaml
MarketSegment:
  id: str
  name: str                        # "Ремонт бытовой техники"
  parent: str                      # дерево сегментов
  aliases: list[str]               # "ремонт холодильников", "fix fridge"
  sellers_count: int
  avg_price: float
  top_sellers: list[Seller]
```

---

## 2. Entity Relationships

### 2.1 Карта связей

```
Source ──→ Listing ──→ Evidence
                          │
                          ├──→ Contact (phone, email, site...)
                          ├──→ Location (address, geo)
                          ├──→ Product (category, brand)
                          ├──→ Photo (hash, watermark)
                          └──→ Text (fingerprint, style)
                               
Evidence ──→ Relationship ──→ Seller
                                │
                                ├──→ Company (через tax_id, legal_name)
                                ├──→ Contact (актуальные способы связи)
                                ├──→ Product (категории, бренды)
                                ├──→ Location (регионы деятельности)
                                └──→ MarketSegment
```

### 2.2 Типы связей

| Связь | Тип | Требует подтверждения | Минимальный Confidence |
|-------|-----|----------------------|----------------------|
| Listing → Evidence | Прямая (извлечение) | Нет | 1.0 |
| Evidence → Seller | Гипотеза (объединение) | Да | ≥0.40 |
| Seller → Company | Гипотеза (регистрация) | Да | ≥0.60 |
| Seller → Contact | Прямая (извлечение) | Нет | 1.0 |
| Seller → Seller | Гипотеза (конкуренты) | Да | ≥0.30 |
| Seller → MarketSegment | Прямая (категория) | Частично | ≥0.70 |

---

## 3. Entity Resolution Model

### 3.1 Match Signals

Сигналы, которые система использует для определения «один продавец или разные»:

| Сигнал | Вес | Надёжность | Риск ложного срабатывания | Источник |
|--------|-----|------------|--------------------------|----------|
| **Телефон** | 0.35 | Высокая | Низкий — телефон редко бывает общим у конкурентов | Прямое извлечение |
| **Email** | 0.30 | Высокая | Низкий | Прямое извлечение |
| **Адрес** | 0.25 | Средняя | Средний — в одном здании может быть много компаний | Парсинг |
| **Фото (хеш)** | 0.20 | Средняя | Средний — фото могут копировать | AI-хеширование |
| **Логотип** | 0.20 | Средняя | Средний — логотип может быть украден | AI-детекция |
| **Текст (fingerprint)** | 0.15 | Средняя | Высокий — шаблонные описания | Семантический анализ |
| **Название** | 0.15 | Низкая | Высокий — «Ремонт холодильников» используют все | Текстовый матчинг |
| **Сайт** | 0.30 | Высокая | Низкий — уникальный домен | Прямое извлечение |
| **Соцсети** | 0.25 | Высокая | Низкий | Парсинг |
| **ИНН/ОГРН** | 0.40 | Очень высокая | Очень низкий — юридически уникален | Официальные данные |
| **Бренды в ассортименте** | 0.15 | Низкая | Высокий — пересечение брендов частое | Кластеризация |
| **График работы** | 0.10 | Низкая | Высокий | Парсинг |
| **Гео-координаты** | 0.35 | Высокая | Средний — торговый центр | GPS-данные |

### 3.2 Комбинация сигналов

Один сигнал **никогда не достаточен** для объединения. Система требует минимум 2 независимых сигнала для confidence ≥ 0.50.

```yaml
merge_rules:
  min_signals: 2                   # минимум независимых сигналов
  min_confidence: 0.50             # минимальный confidence для гипотезы
  one_dominant_allowed: false      # нельзя полагаться только на один сигнал
  require_independent: true        # сигналы должны быть из разных категорий
```

Пример корректного объединения:

```yaml
seller_match:
  entity_a: "seller_001"  # "Ремонт холодильников Иванов" на Avito
  entity_b: "seller_042"  # "Холод-Сервис" на Юле
  
  confidence: 0.72
  signals:
    - phone: "+7 (999) 123-45-67"         # вес 0.35
    - address: "ул. Ленина, 10, оф. 5"    # вес 0.25
    - geo: [55.75, 37.62]                  # вес 0.12 (дополнительный)
  
  total_before_negative: 0.72
  negative_signals: []                    # нет противоречий
  
  decision: POSSIBLE_MATCH
  requires_review: true
```

---

## 4. Confidence System

### 4.1 Шкала уверенности

| Диапазон | Уровень | Цвет | Действие | Пример |
|----------|---------|------|----------|--------|
| 0–30% | **None** | ⚪ | Ничего не делать. Сохранить как гипотезу. | Случайное совпадение города |
| 30–55% | **Possible** | 🟡 | Отметить для ручной проверки. Не использовать в анализе. | Один общий телефон, всё разное |
| 55–75% | **Candidate** | 🟠 | Включить в анализ с пометкой. Предложить пользователю. | 2–3 сигнала, частичные совпадения |
| 75–92% | **Strong** | 🟢 | Использовать в анализе. AI может действовать. | 3+ независимых сигнала |
| 92–99% | **Verified** | 🔵 | Считать установленным. Автоматическое объединение. | 5+ сигналов, включая юридические |
| 99%+ | **Certain** | 💎 | Юридически подтверждено. Не оспаривается без новых данных. | ИНН, выписка ЕГРЮЛ |

### 4.2 Разрешённые действия по уровню

| Действие | None | Possible | Candidate | Strong | Verified | Certain |
|----------|------|----------|-----------|--------|----------|---------|
| Сохранить гипотезу | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Показать пользователю | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Использовать в анализе | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ |
| Автоматическое объединение | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Автоматическое действие | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |

---

## 5. Evidence Model

### 5.1 Proof Chain

Каждое решение должно быть воспроизводимо через цепочку доказательств.

```
Listing A (Avito)
  ↓ извлечение поля "phone"
Evidence: same_phone (+0.35)
  ↓
Listing B (Юла)
  ↓ извлечение поля "phone"
Evidence: same_phone (подтверждение, +0.35 — уже учтено)
  ↓
Listing B (Юла)
  ↓ извлечение поля "address"
Evidence: same_address (+0.25)
  ↓
Listing C (сайт компании)
  ↓ извлечение логотипа
Evidence: same_logo (+0.20)
  ↓
  ┌─────────────────────────────────────┐
  │ Итого: 0.35 + 0.25 + 0.20 = 0.80  │
  │ Decision: STRONG                    │
  │ Объединить: Seller_A + Seller_B    │
  └─────────────────────────────────────┘
```

### 5.2 Воспроизводимость

Любой вывод можно развернуть:
- Какие Evidence были использованы
- Какие веса имели
- Какие Negative Evidence были учтены
- Какое решение принято
- Кто принял решение (AI / человек / правило)

---

## 6. Data Immutability

### 6.1 Что нельзя менять

- Listing — original raw data никогда не перезаписывается
- Evidence — никогда не удаляется
- Audit Trail — каждое действие фиксируется
- Историю confidence — старые значения сохраняются

### 6.2 Что можно добавлять

- Новые Evidence (дополняющие или опровергающие)
- Новые версии Seller (с указанием superseded_by)
- Исправления ошибок (как correcting evidence)
- Результаты ручной верификации

### 6.3 Версионирование

```yaml
listing_avito_123:
  v1: 2026-07-16T10:00:00Z  # оригинальная версия
  v2: 2026-07-16T14:00:00Z  # цена изменилась (новый парсинг)
  history:
    - v1: { price: 50000, status: active }
    - v2: { price: 45000, status: active }
```

---

## 7. Minimum Viable Model

### 7.1 Обязательные сущности для MVP

| Сущность | Причина |
|----------|---------|
| **Source** | Знать, откуда данные |
| **Listing** | Хранить исходные наблюдения |
| **Evidence** | Основа всех решений системы |
| **Seller** | Главный объект анализа |

### 7.2 Отложенные сущности

| Сущность | Когда добавлять |
|----------|-----------------|
| Company | После первых 1000 объединений |
| Contact | Вместе с Company |
| Product | После стабилизации Entity Resolution |
| Location | При расширении на недвижимость |
| MarketSegment | При > 1000 Seller |
| Relationship Graph | При > 5000 Seller |

### 7.3 MVP в числах

```
Объявлений:       от 50 до 500
Seller (auto):    неизвестно (результат анализа)
Seller (manual):  минимум 10 для валидации
Evidence:         минимум 3 на одно объединение
Confidence:       фиксируется, но не управляется AI
Верификация:      100% ручная
```

---

## 8. Future Extensions

| Расширение | Когда | Что меняется |
|-----------|-------|-------------|
| **Графовая БД** (Neo4j/ArangoDB) | > 10 000 Seller | Relationship — ключевой объект |
| **ML Entity Resolution** | > 1000 верифицированных объединений | Веса evidence настраиваются ML |
| **Автоматический анализ рынка** | > 100 Seller/сегмент | MarketSegment — активный объект |
| **Прогноз возможностей** | > 6 месяцев данных | Opportunity Engine |
| **Внешние API** (ФНС, ЕГРЮЛ) | При масштабировании | Company — верифицируемая сущность |
| **Временные ряды** | > 3 месяцев данных | PriceHistory, Seasonality |

---

## 9. Architectural Rule

> **Мы моделируем реальный рынок, а не страницы сайтов.**

Listing — лишь временное свидетельство. Evidence — основа решений. Seller — гипотеза, пока не доказана.

Система не спрашивает «как выглядит объявление». Она спрашивает «кто стоит за этим объявлением, и как это доказать».

---

## Приложение: Глоссарий

| Термин | Определение |
|--------|-------------|
| **Listing** | Сырое наблюдение — единичное объявление с площадки |
| **Evidence** | Извлечённый признак — доказательство существования связи |
| **Seller** | Гипотетический участник рынка — результат объединения |
| **Company** | Юридическая сущность — верифицированный участник |
| **Signal** | Тип evidence (phone, address, photo...) |
| **Confidence** | Числовая мера уверенности в выводе |
| **Proof Chain** | Цепочка evidence, ведущая к выводу |
| **Entity Resolution** | Процесс определения «один или разные» |
| **False Merge** | Ошибочное объединение разных сущностей |
| **False Split** | Ошибочное разделение одной сущности |
