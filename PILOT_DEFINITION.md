# Pilot Definition — Market Intelligence OS v1.0

> *До сбора данных фиксируем критерии успеха, формат результата и правила остановки.*

---

## 1. Business Question

> **Найти компании ремонта бытовой техники в регионе, которые имеют коммерческий потенциал для цифрового расширения.**

### Подвопросы:

1. Какие компании реально работают в нише? (Entity Accuracy)
2. У кого слабая цифровая представленность? (Opportunity)
3. Кому можно предложить услугу? (Lead)
4. Какие источники дают максимальную ценность? (Source Quality)

---

## 2. Target User

### Первичный пользователь

```yaml
type: business_developer / sales
goal: найти клиентов для B2B-услуги
pain: ручной поиск по десяткам площадок
decision: кому звонить / писать на этой неделе
```

### Вторичный пользователь

```yaml
type: marketing_analyst
goal: понять структуру рынка
pain: нет целостной картины
decision: какой канал усилить
```

---

## 3. Success Criteria

### Основные метрики

| Метрика | Цель | Минимум | Приоритет |
|---------|------|---------|-----------|
| **Entity Accuracy** | > 95% | > 85% | Критично |
| **False Merge Rate** | 0% | < 2% | Критично |
| **False Split Rate** | < 10% | < 20% | Средний |
| **Opportunity Precision** | > 50% | > 30% | Высокий |
| **Lead Usefulness** | > 30% | > 15% | Высокий |
| **Evidence Coverage** | > 80% | > 60% | Средний |

### Определения

```yaml
entity_accuracy:
  definition: "Сущность в графе соответствует реальному участнику рынка"
  measurement: "50 случайных сущностей проверяются человеком"

false_merge:
  definition: "Два разных продавца объединены в одного"
  measurement: "0 — критично, любое число > 0 требует остановки"

opportunity_precision:
  definition: "Найденная возможность реально существует"
  measurement: "% от проверенных"

lead_usefulness:
  definition: "На лид можно совершить бизнес-действие"
  measurement: "% от проверенных"
```

---

## 4. Output Format

### Результат пилота

```
Не: "Вот 100 компаний"

А: "Вот 20 проверенных возможностей"
```

### Формат каждого результата

```yaml
entity:
  name: "ООО Ремонт+"
  type: company
  confidence: 0.92

evidence_chain:
  - source: yandex_maps
    signals: [address, website]
  - source: avito
    signals: [phone, activity]
  - source: company_website
    signals: [domain, contacts]

why_selected:
  - "активность на 3 площадках"
  - "нет собственного сайта"
  - "верифицирован через Яндекс Карты"

opportunity:
  type: digital_expansion
  confidence: 0.82
  evidence: ["нет сайта при наличии на 3 площадках"]

lead:
  type: digital_expansion
  score: 82/100
  recommended_action: "Предложить создание сайта / цифрового канала"
```

---

## 5. Pilot Parameters

```yaml
domain: "Ремонт бытовой техники"
region: "Москва"  # один регион для первого пилота

dataset_size: 100
human_validation_size: 50

sources:
  - yandex_maps: true
  - avito: true
  - company_website: true
  - yandex_market: true
  - ozon: true
  - wildberries: true

pipeline:
  - source_collection
  - normalize
  - evidence_extraction
  - entity_resolution
  - graph_build
  - opportunity_scan
  - lead_generation
```

---

## 6. Human Validation Rules

### Что считается

```yaml
true_entity:
  conditions:
    - "реальный участник рынка"
    - "можно найти в открытых источниках"
    - "оказывает заявленные услуги"

useful_opportunity:
  conditions:
    - "возможность реально существует"
    - "можно проверить по данным"
    - "имеет коммерческий смысл"

qualified_lead:
  conditions:
    - "можно совершить бизнес-действие"
    - "есть контакт или канал"
    - "потенциальная ценность > затрат на контакт"
```

### Процесс валидации

```yaml
step_1: "человек открывает сущность из графа"
step_2: "человек проверяет по источникам (3-5 минут на сущность)"
step_3: "заполняет форму"
  - Это реальный продавец? (YES / NO)
  - False Merge? (YES / NO)  
  - Есть полезная возможность? (YES / NO)
  - Это качественный лид? (YES / NO)
  - Комментарий
step_4: "результат записывается в validation_log"
```

---

## 7. Pilot Stop Conditions

### Немедленная остановка

```yaml
stop_if:
  - condition: "false_merge_rate > 2%"
    action: "Остановить. Проверить Entity Resolution."
  
  - condition: "entity_accuracy < 70%"
    action: "Остановить. Проверить источники."
  
  - condition: "нет evidence у > 40% сущностей"
    action: "Остановить. Проверить качество данных."
```

### Продолжение с оговорками

```yaml
continue_with_caveats_if:
  - condition: "entity_accuracy 70-85%"
    action: "Продолжить, но зафиксировать проблемы с данными"
  
  - condition: "opportunity_precision 15-30%"
    action: "Продолжить, но улучшить Opportunity Engine"
```

---

## 8. Outputs

```yaml
pilot_dataset_v1:
  entities.json:      "100 сущностей с evidence chain"
  evidence.json:      "все извлечённые доказательства"
  relationships.json: "связи между сущностями"
  opportunities.json: "найденные возможности"
  leads.json:         "сгенерированные лиды"
  validation_log.json: "50 человеческих проверок"

validation_report:
  file: "PILOT_VALIDATION_REPORT.md"
  content:
    - entity_accuracy
    - false_merge_rate
    - false_split_rate
    - opportunity_precision
    - lead_usefulness
    - best_signals
    - worst_signals
    - product_decision (pass / improve / stop)
```

---

## 9. Final Principle

> **Количество сущностей не делает пилот успешным. Решение, которое можно принять на основе данных — делает.**

100 сущностей, прошедших human validation, ценнее 10 000 сырых записей без проверки.
