# First Commercial Intelligence Report

> *Market Intelligence OS — первый коммерческий сценарий*

---

## Сценарий: Поиск клиентов для бизнеса (Finding Business Opportunities)

### Ниша: Ремонт бытовой техники

---

## Pipeline

```
Market Graph
      ↓
Opportunity Engine (8 сигналов)
      ↓
4 Lead Rules
      ↓
Lead Scorer (6 компонентов)
      ↓
Рекомендация
```

---

## Lead Rules

| Правило | Тип | Приоритет | Описание |
|---------|-----|-----------|----------|
| **RULE_001** | digital_expansion | 🔴 high | Verified seller + no website + multiple sources |
| **RULE_002** | channel_diversification | 🟡 medium | Marketplace seller + no owned channel |
| **RULE_003** | growth_opportunity | 🟡 medium | High activity + weak presence |
| **RULE_004** | local_presence_gap | 🟢 low | Verified + phone + limited geography |

---

## Lead Score (0-100)

| Компонент | Макс | Описание |
|-----------|------|----------|
| Верификация | 20 | Статус verified/candidate |
| Evidence | 20 | Количество доказательств |
| Источники | 20 | Разнообразие каналов |
| Контакты | 15 | Наличие телефона/сайта |
| Возможности | 15 | Количество найденных сигналов |
| Приоритет | 10 | high/medium/low |

Score **всегда объясним** — каждый Lead содержит `score_breakdown`.

---

## Пример: Digital Expansion Lead

```text
Entity:        ООО Техно
Type:          digital_expansion
Score:         82/100
Priority:      high
Status:        new

Evidence:
  → Активность на 3 площадках
  → Сайт не обнаружен
  → 💡 Создание / продвижение сайта

Score Breakdown:
  +20 verified_entity
  +8 evidence_count (2 доказательства)
  +15 source_diversity (3 источника)
  +8 contact_availability
  +10 opportunity_count
  +10 priority
  +9 graph_relationships

Рекомендация: Предложить создание сайта / цифрового канала
```

---

## Golden Dataset Validation

| Entity | Phone | Website | Лиды | Результат |
|--------|-------|---------|------|-----------|
| **Стирком.ру** | ✅ | ✅ stirkom.ru | Нет digital_expansion | ✅ Корректно |
| **Либхерр Сервис** | ✅ | ✅ liebherr-service.ru | Нет digital_expansion | ✅ Корректно |

Оба имеют сайт — Digital Expansion лиды не создаются. **False recommendation protection работает.**

---

## Тесты

```
12/12 тестов коммерческого модуля
         +
132 теста основного стека
         =
144 теста, 0 failures, 0% False Merge
```

---

## Принципы

| Принцип | Статус |
|---------|--------|
| Каждый Lead имеет Evidence chain | ✅ |
| Score всегда объясним | ✅ |
| Нет hallucinated facts | ✅ |
| Нет автоматических решений | ✅ |
| False recommendation protection | ✅ |

---

## Следующие шаги

| Шаг | Описание |
|-----|----------|
| **4.2** | Human Review Dashboard — управление лидами |
| **4.3** | Первый реальный лид из Market Graph + ручная верификация |
| **4.4** | CRM/Automation — отправка рекомендаций |

---

*Market Intelligence OS · First Commercial Report*
