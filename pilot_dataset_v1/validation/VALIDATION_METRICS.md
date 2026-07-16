# Validation Metrics — Phase 5.2

> *Human Validation Results for Phase 5.1 Pilot*

---

## Sample

```yaml
total_reviews: 45
  auto_validated: 3  (Golden Dataset known entities)
  pending_human: 42

stratification:
  high_confidence (score >= 60): 20
  medium_confidence (score 40-59): 15
  low_confidence (score < 40): 10
```

---

## Auto-Validation Results

Из 45 проверок 3 выполнены автоматически (Golden Dataset):

| Entity | Type | Score | Entity OK | Opportunity Useful | Lead OK |
|--------|------|-------|-----------|-------------------|---------|
| Либхерр Сервис | digital_expansion | 60 | ✅ YES | ❌ (has website) | ❌ (has website) |
| Стирком.ру | digital_expansion | 64 | ✅ YES | ❌ (has website) | ❌ (has website) |
| ИП Чиликов А.А. | channel_diversification | 68 | ✅ YES | ❌ (has website) | ❌ (has website) |

### Вывод

Все 3 известные сущности опознаны правильно (100% Entity Precision). Однако Opportunity Engine сгенерировал leads для сущностей, которые уже имеют полную цифровую представленность — это **ложные срабатывания**.

---

## Ожидаемые метрики после полной валидации

| Метрика | Текущая | Цель | Статус |
|---------|---------|------|--------|
| Entity Precision | **100%** (3/3) | > 95% | 🟢 |
| False Merge | **0%** | 0% | 🟢 |
| Opportunity Precision | **0%** (3 auto) | > 50% | 🔴 |
| Lead Actionable | **0%** (3 auto) | > 30% | 🔴 |

---

## Ошибки (auto-validation)

### TYPE C: False Opportunity

```yaml
entity: Либхерр Сервис
lead_type: digital_expansion
score: 60/100
проблема: У сущности есть и сайт (liebherr-service.ru) и телефон
результат: NOT useful → False Positive
```

### TYPE D: Bad Lead Recommendation

```yaml
entity: ИП Чиликов А.А.
lead_type: channel_diversification
score: 68/100
проблема: У сущности есть site + phone + inn → lead не нужен
результат: NOT actionable → False Positive
```

---

## Рекомендация

```yaml
entity_resolution: PASS ✅
opportunity_engine: IMPROVE NEEDED
  проблема: слишком много false positives
  причина: weak_digital_presence не проверяет наличие phone/website
  фикс: добавить фильтр "есть website → skip weak_digital_presence"

lead_generation: IMPROVE NEEDED
  проблема: leads создаются для сущностей, не нуждающихся в услуге
  причина: нет проверки контактов перед созданием lead
  фикс: digital_expansion требует отсутствия и website, и phone
```

---

## Статус

```yaml
pipeline: PASS
entity_resolution: PASS
opportunity_quality: ⚠️ NEEDS EVIDENCE FILTER
lead_quality: ⚠️ NEEDS CONTACT CHECK

phase_5_decision: IMPROVE
action: "Добавить фильтр контактов в Opportunity Engine + Lead Generator"
```

---

## Следующий шаг

1. Заполнить 42 оставшиеся human reviews
2. Обновить метрики
3. Применить фильтры в Opportunity Engine
4. Повторный прогон пилота
