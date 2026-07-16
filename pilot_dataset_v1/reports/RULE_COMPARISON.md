# Rule Comparison — v1 vs Candidate Rules

> *Сравнение текущих правил с кандидатами на основе offline replay*

---

## OPP-001 — Weak Digital Presence

| | v1 (active) | v2 (candidate) |
|---|---|---|
| **Rule** | `has_listings AND NOT has_website` | `has_listings AND NOT has_website AND NOT has_phone` |
| **Precision** | 0% (3 FPs) | est. 100% |
| **Leads** | 95 digital_expansion | 91 digital_expansion (-4) |
| **FP eliminated** | — | 3/3 (100%) |
| **TP affected** | — | 0 |
| **Status** | ⬅️ active | **→ PROMOTE** |

## LEAD-001 — Digital Expansion Lead

| | v1 (active) | v2 (candidate) |
|---|---|---|
| **Rule** | inherits OPP-001 | inherits OPP-001-v2 |
| **Precision** | 0% (inherited) | est. 100% |
| **Leads** | all digital_expansion | filtered |
| **FP eliminated** | — | 3/3 (100%) |
| **Status** | ⬅️ active | **→ PROMOTE** |

## OPP-004 — Evidence Confidence Gate (NEW)

| | v1 (experimental) |
|---|---|
| **Rule** | `min_evidence_confidence >= 0.70` |
| **Precision** | unknown — needs measurement |
| **Leads affected** | 0 in current dataset |
| **Risk** | may filter real opportunities with thin data |
| **Status** | **→ KEEP EXPERIMENTAL** |

---

## Decision

```yaml
promote:
  - OPP-001-v2
  - LEAD-001-v2

keep_experimental:
  - OPP-004-v1

reject:
  - (none)
```
