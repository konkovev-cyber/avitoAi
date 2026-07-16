# Rule Registry — Opportunity Engine Signal Rules

> *Каждое изменение правила измеримо через Precision / Recall.*

---

## OPP-001 — Weak Digital Presence

**Версия v1 (deprecated)**

```yaml
rule: "has_listings AND NOT has_website → weak_digital_presence"
precision: 0% (0/3 на Golden Dataset)
recall: 100%
false_positives:
  - Либхерр Сервис (has website, has phone)
  - Стирком.ру (has website, has phone)
  - ИП Чиликов А.А. (has website, has phone)
причина_ошибки: "не проверяет has_phone — сущности с сайтом всё равно попадают"
```

**Версия v2 (candidate)**

```yaml
rule: "has_listings AND NOT has_website AND NOT has_phone → weak_digital_presence"
hypothesis: "только если нет ни сайта, ни телефона — это real opportunity"
precision: "?"
recall: "?"
status: "экспериментальная — требует проверки"
```

---

## OPP-002 — Marketplace Dependency

**Версия v1 (active)**

```yaml
rule: "single_source == marketplace → marketplace_dependency"
precision: "?"
recall: "?"
note: "не тестировалась на Golden Dataset — нет marketplace-сущностей в GD"
```

---

## OPP-003 — Single Source Risk

**Версия v1 (active)**

```yaml
rule: "single_source AND verified → single_source_risk"
precision: "?"
recall: "?"
note: "может давать false positives для intentionally single-source businesses"
```

---

## LEAD-001 — Digital Expansion Lead

**Версия v1 (deprecated)**

```yaml
rule: "opportunity weak_digital_presence → digital_expansion lead"
precision: 0%
причина: "наследует ошибки OPP-001"
```

**Версия v2 (candidate)**

```yaml
rule: "opportunity weak_digital_presence AND NOT has_website AND NOT has_phone → digital_expansion"
precision: "?"
status: "зависит от OPP-001 v2"
```

---

## Сводная таблица

| Rule ID | Версия | Precision | Recall | FP | FN | Статус |
|---------|--------|-----------|--------|----|-----|--------|
| OPP-001 | v1 | 0% | 100% | 3 | 0 | deprecated |
| OPP-001 | v2 | ? | ? | ? | ? | candidate |
| OPP-002 | v1 | ? | ? | ? | ? | active |
| OPP-003 | v1 | ? | ? | ? | ? | active |
| LEAD-001 | v1 | 0% | 100% | 3 | 0 | deprecated |
| LEAD-001 | v2 | ? | ? | ? | ? | candidate |

---

## История изменений

| Дата | Rule | Версия | Изменение |
|------|------|--------|-----------|
| 2026-07-16 | OPP-001 | v1 | Создана: has_listings AND NOT has_website |
| 2026-07-16 | OPP-001 | v1→v2 | Обнаружены false positives (Либхерр, Стирком, ИП Чиликов). Гипотеза: добавить NOT has_phone |
| 2026-07-16 | LEAD-001 | v1 | Создана: наследует OPP-001 |
| 2026-07-16 | LEAD-001 | v1→v2 | Зависит от OPP-001 v2 |
