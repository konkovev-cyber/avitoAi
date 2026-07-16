# Pilot Decision — Phase 5.1 / 5.2

> *Решение по итогам первого коммерческого пилота*

---

## Executive Summary

```yaml
entities_collected: 100
pipeline_execution: PASS
auto_validation: 3/45 (Golden Dataset)
human_validation: 42/45 pending

entity_precision: 100% (3/3) — 🟢
opportunity_precision: 0% (0/3) — 🔴 (false positives)
lead_usefulness: 0% (0/3) — 🔴 (false positives)
```

---

## Что подтверждено

| Компонент | Статус | Доказано |
|-----------|--------|----------|
| **Connector Layer** | ✅ | 6 источников → единый Listing |
| **Evidence Extraction** | ✅ | Телефон, сайт, адрес, ИНН |
| **Entity Resolution** | ✅ | 100% precision на известных сущностях |
| **Market Graph** | ✅ | Сущности + связи + evidence |
| **Pipeline** | ✅ | End-to-end за < 1 мин |
| **Golden Dataset** | ✅ | Все тесты пройдены (144) |

---

## Что требует улучшения

| Компонент | Проблема | Причина |
|-----------|----------|---------|
| **Opportunity Engine** | False positives | Не проверяет наличие контактов |
| **Lead Generator** | Избыточные лиды | Не фильтрует сущности с website/phone |

---

## Решение

```yaml
decision: IMPROVE

scope:
  - opportunity_engine: true
  - lead_generator: true
  - entity_resolution: false
  - connectors: false
  - pipeline: false

reason: "Entity Resolution работает. Opportunity Engine генерирует false positives."

action:
  - "Добавить фильтр: has_website → skip weak_digital_presence"
  - "Добавить фильтр: has_phone AND has_website → skip все leads"
  - "Перезапустить пилот после фильтрации"
```

---

## Требования к IMPROVE

### Opportunity Engine

```yaml
weak_digital_presence:
  condition: "NOT has_website AND NOT has_phone"
  current: "только NOT has_website"  # причина false positive

no_phone:
  condition: "NOT has_phone"
  current: "correct"

no_website:
  condition: "NOT has_website"
  current: "correct"
```

### Lead Generator

```yaml
digital_expansion:
  rule: "Только если нет website AND нет phone"
  current: "если нет website"  # причина false positive
```

---

## После IMPROVE

```yaml
step_1: apply_filters
  ожидание: opportunity false positives → 0

step_2: rerun_pilot
  ожидание: leads quality → улучшение

step_3: revalidate
  ожидание: opportunity precision > 50% → PASS
```

---

## Decision Tree

```yaml
current_state:
  entity_resolution: PASS ✅
  opportunity_engine: NEEDS FIX 🔧
  lead_quality: NEEDS FIX 🔧

if_fix_successful:
  entity: PASS
  opportunity: PASS
  leads: PASS
  → Phase 6 Productization 🚀

if_fix_unsuccessful:
  → Architecture Review
```

---

*Market Intelligence OS · Pilot Decision v1*
