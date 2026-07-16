# Failure Taxonomy — Opportunity Engine v1

> *Классификация ложноположительных срабатываний*

---

## FP001 — Has Website, Lead Still Created

```yaml
count: 3
severity: high
cause: OPP-001 проверяет только has_listings, не проверяет has_website
example: Либхерр Сервис (liebherr-service.ru) → digital_expansion lead
fix: OPP-001-v2 — добавить NOT has_website
```

## FP002 — Has Phone, Lead Still Created

```yaml
count: 0 (на validation set)
severity: high
cause: OPP-001 не проверяет has_phone
example: не обнаружено в текущем датасете
fix: OPP-001-v2 — добавить NOT has_phone
```

## FP003 — Has Website AND Phone, Lead Still Created

```yaml
count: 3
severity: critical
cause: OPP-001 не имеет фильтра контактов
entities:
  - Либхерр Сервис (website + phone + inn)
  - Стирком.ру (website + phone)
  - ИП Чиликов А.А. (website + phone + inn)
fix: OPP-001-v2 — NOT has_website AND NOT has_phone
```

## Статистика

| Тип | Count | % of validated | Severity |
|-----|-------|---------------|----------|
| FP001 | 3 | 100% | high |
| FP002 | 0 | 0% | high |
| FP003 | 3 | 100% | critical |
| **Total FPs** | **3** | **100%** | — |
