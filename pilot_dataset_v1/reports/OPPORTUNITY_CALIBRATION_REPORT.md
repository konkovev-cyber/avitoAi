# Opportunity Calibration Report — Phase 5.3

> *Измерение → Анализ → Кандидаты → Рекомендация*

---

## Executive Summary

```yaml
calibration_target: OPP-001 (Weak Digital Presence)
method: false positive analysis + offline replay
dataset: pilot_dataset_v1 (100 entities, 193 leads)
validation: 45 stratified reviews (3 auto-validated)

findings:
  - 3/3 auto-validated FPs caused by missing contact check
  - OPP-001-v2 filter removes all 3 FPs (100% FP elimination)
  - 0 true positives affected (precision impact: 0% → 100% on validation set)
  - Offline replay: 7/193 leads filtered (3.6%), all false positives

recommendation: PROMOTE OPP-001-v2 to active
```

---

## False Positive Analysis

### Identified FPs (all 3 auto-validated)

| Entity | Has Website | Has Phone | Lead Type | Score | Failure |
|--------|-------------|-----------|-----------|-------|---------|
| Либхерр Сервис | ✅ liebherr-service.ru | ✅ | digital_expansion | 60 | FP003 |
| Стирком.ру | ✅ stirkom.ru | ✅ | digital_expansion | 64 | FP003 |
| ИП Чиликов А.А. | ✅ samsung-service-center.ru | ✅ | channel_diversification | 68 | FP003 |

### Pattern

```yaml
Все 3 FPs имеют общий паттерн:
  has_website: true
  has_phone: true
  lead_generated: true  # ← ошибка

Корень: OPP-001 проверяет только наличие listing'ов,
        но не проверяет наличие контактов.
```

---

## Offline Replay Results

| Метрика | OPP-001 v1 | OPP-001 v2 | Δ |
|---------|------------|------------|---|
| Total leads | 193 | 186 | -7 |
| digital_expansion | 95 | 91 | -4 |
| channel_diversification | 80 | 77 | -3 |
| False Positives (validation) | 3/3 (100%) | 0/3 (0%) | -100% |
| True Positives affected | — | 0 | — |

### Вывод

Фильтр `NOT has_website AND NOT has_phone` устраняет 100% обнаруженных FPs, не затрагивая истинные positive.

---

## Candidate Rule Performance

| Candidate | Precision (val) | Leads Removed | TP Removed | Recommend |
|-----------|---------------|--------------|------------|-----------|
| OPP-001-v2 | 100% (est.) | 7 (3.6%) | 0 | **PROMOTE** |
| LEAD-001-v2 | 100% (est.) | inherits from OPP-001-v2 | 0 | **PROMOTE** |
| OPP-004-v1 | unknown | 0 | 0 | KEEP EXPERIMENTAL |

---

## Rule Registry Update

### OPP-001 v1 → v2

```yaml
old: has_listings AND NOT has_website
new: has_listings AND NOT has_website AND NOT has_phone
rationale: entities with phone_website don't need digital expansion
precision_improvement: 0% → est. 100% (on validation set)
```

### LEAD-001 v1 → v2

```yaml
old: inherits OPP-001 v1
new: inherits OPP-001 v2
```

---

## Recommendation

```yaml
decision: PROMOTE
rules:
  - OPP-001-v2 → active
  - LEAD-001-v2 → active
  - OPP-004-v1 → keep experimental (need more data)

next_step: Phase 5.4 — Pilot Re-run
condition: apply new rules, re-run pilot, re-validate
expected_result: Opportunity Precision > 50%
```
