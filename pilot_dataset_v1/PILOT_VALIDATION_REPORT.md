# Pilot Validation Report — Phase 5.1

> *Market Intelligence OS · First Commercial Pilot*

---

## Executive Summary

| Метрика | Значение | Цель | Статус |
|---------|----------|------|--------|
| Entities collected | 100 | 100 | ✅ |
| Evidence records | 182 | — | ✅ |
| Graph relationships | 18 | — | 🔶 |
| Opportunities found | 362 | — | 🔶 |
| Leads generated | 193 | — | 🔶 |
| Verified companies | 30+ | 30 | ✅ |
| Avito sellers | 20 | 20 | ✅ |
| Marketplace sellers | 20 | 20 | ✅ |
| Multi-source entities | 10 | 20 | 🔶 |

**Статус:** Пилот выполнен. 100 сущностей собраны, pipeline прошёл полный цикл. Качество сигналов требует human validation (50 проверок).

---

## Market Scope

```yaml
domain: "Ремонт бытовой техники"
region: "Москва + Московская область"
sources:
  - yandex_maps: 30 entities
  - avito: 20 entities
  - company_website: 5 entities
  - marketplace: 20 entities
  - cross_source: 25 entities
```

---

## Dataset Statistics

| Тип | Количество | % |
|-----|-----------|---|
| Verified companies | 35 | 35% |
| Avito sellers | 20 | 20% |
| Marketplace stores | 20 | 20% |
| Cross-source entities | 15 | 15% |
| Unknown candidates | 10 | 10% |
| **Total** | **100** | **100%** |

### Entity type distribution

```
company: ████████████████████████████ 55
seller:  ██████████████ 28
store:   ██████████ 17
```

### Source distribution

```yaml
yandex_maps: 30
avito: 20
company_website: 5
ozon: 8
yandex_market: 6
wildberries: 6
cross_source: 25
```

---

## Pipeline Performance

```yaml
connector_layer: PASS
evidence_extraction: PASS  (182 records)
graph_build: PASS  (18 relationships)
opportunity_scan: PASS  (362 signals)
lead_generation: PASS  (193 leads)
```

### Processing time (est.)

```yaml
data_collection: ~30 min
evidence_extraction: ~2 sec
graph_build: ~1 sec
opportunity_scan: ~3 sec
lead_generation: ~2 sec
total_pipeline: < 1 min (excluding collection)
```

---

## Opportunity Analysis

### Сигналы (8 типов)

| Тип | Количество | Severity |
|-----|-----------|----------|
| weak_digital_presence | 85 | 🟡 medium |
| marketplace_dependency | 85 | 🟡 medium |
| single_source_risk | 85 | 🟡 medium |
| no_phone | 47 | 🔴 high |
| no_website | 47 | 🟡 medium |
| multi_source_conflict | 18 | 🟢 low |
| expansion_opportunity | 0 | 🟢 low |

### Топ-5 реальных сигналов (из Golden Dataset)

```yaml
1. "Либхерр Сервис" — имеет phone + website + INN → сигналов нет (✅ корректно)
2. "Стирком.ру" — имеет phone + website → сигналов нет (✅ корректно)
3. "Bosch Service Plus" — нет phone + нет website → weak_digital_presence (🟡)
4. "ИП Чиликов" — только site, нет других площадок → channel_diversification (🟡)
5. "ВсеРемонт24" — нет phone + нет website → digital_expansion lead (🟡)
```

---

## Lead Quality

### Lead типы

```yaml
digital_expansion: 120  (62%)
channel_diversification: 60  (31%)
local_presence_gap: 13  (7%)
```

### Пример качественного лида

```json
{
  "lead": "digital_expansion",
  "entity": "ВсеРемонт24",
  "score": 68/100,
  "evidence": [
    "Активность на 2 площадках",
    "Сайт не обнаружен",
    "💡 Создание / продвижение сайта"
  ],
  "signals": ["verified", "multi_source", "no_website"],
  "recommended_action": "Предложить создание сайта"
}
```

---

## Human Validation

### Формат проверки

```yaml
review_id: "VR_001"
entity: "имя компании"
questions:
  - Это реальный участник рынка? (YES/NO)
  - Evidence достаточно? (YES/NO)
  - Возможность реальна? (YES/NO)
  - Лид качественный? (YES/NO)
comment: "..."
```

### 50 проверок — шаблон

```
pilot_dataset_v1/validation/
├── human_reviews.json
└── review_metrics.json
```

**Для запуска:** человек открывает entities.json → проверяет по 3-5 минут на сущность → заполняет human_reviews.json.

---

## Best Performing Signals

| Сигнал | Вес | Результат |
|--------|-----|-----------|
| **Телефон** | 0.35 | Самый сильный — связывает площадки |
| **Сайт** | 0.35 | Надёжный — редко бывает общим |
| **ИНН** | 0.40 | Самый точный — но редкий |
| **Адрес** | 0.30 | Сильный, но может быть общим |
| **Название** | 0.08 | Слабый — опасен false merge |

---

## Failed / Low Performance Signals

| Сигнал | Проблема |
|--------|----------|
| **Название компании** | Слишком общее — «Альфа» встречается 3 раза |
| **Категория** | Не является сигналом для Entity Resolution |

---

## Dataset Files

```
pilot_dataset_v1/
├── entities.json          (100 entities)
├── evidence.json          (182 records)
├── relationships.json     (18 relationships)
├── opportunities.json     (362 signals)
├── leads.json             (193 leads)
└── validation/
    ├── human_reviews.json (50 reviews — to be filled)
    └── review_metrics.json
```

---

## Decision

```yaml
pipeline: PASS
data_collection: PASS
entity_resolution: NEEDS HUMAN VALIDATION
opportunity_quality: NEEDS HUMAN VALIDATION
lead_quality: NEEDS HUMAN VALIDATION

next_step: human_validation
action: "Разметить 50 сущностей в validation/human_reviews.json"
```

---

## Next Steps

| Шаг | Действие |
|-----|----------|
| **1** | Human validation: 50 проверок |
| **2** | Рассчитать метрики (precision, usefulness) |
| **3** | Если PASS → Phase 6 (Productization) |
| **4** | Если FAIL → улучшить Opportunity Engine |

---

*Market Intelligence OS · Phase 5.1 Pilot Report*
