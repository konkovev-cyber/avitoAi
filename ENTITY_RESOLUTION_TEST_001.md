# Entity Resolution Test #001 — Golden Dataset Protocol

> *Мы сначала учим систему понимать рынок, а потом масштабируем сбор данных.*

---

## 1. Test Objective

### 1.1 Что проверяем

| Аспект | Вопрос |
|--------|--------|
| **Match Signals** | Какие сигналы реально работают, какие шумят |
| **Confidence Score** | Насколько AI-оценка совпадает с человеческой |
| **False Merge Rate** | Как часто система объединяет разных продавцов |
| **False Split Rate** | Как часто система разделяет одного продавца |
| **Evidence Coverage** | Какой процент связей подкреплён доказательствами |

### 1.2 Гипотезы эксперимента

```yaml
hypotheses:
  - phone_is_strongest: true       # телефон — самый надёжный сигнал
  - address_is_ambiguous: true     # адрес часто даёт ложные срабатывания
  - title_is_noise: true           # название — почти бесполезно для resolution
  - photo_hash_reliable: true      # хеш фото надёжен, но фото воруют
  - text_template_problem: true    # шаблонные описания создают ложные совпадения
```

### 1.3 Главный принцип

> **False Merge хуже False Split.**

Лучше оставить 2 гипотетических Seller и потом вручную объединить, чем ошибочно смержить конкурентов и потерять рыночную картину.

---

## 2. Dataset

### 2.1 Размер и структура

```yaml
total_listings: 50
  sources:
    - avito: 20
    - youla: 15
    - vk_market: 10
    - telegram: 5
  
  estimated_real_sellers: 10–15
  listings_per_seller: 2–5
  
  categories:
    - electronics: 15    # телефоны, ноутбуки
    - services: 15       # ремонт, клининг
    - auto: 10           # запчасти, шины
    - home: 10           # мебель, техника
```

### 2.2 Критерии отбора

Объявления подбираются так, чтобы создать **реалистичную картину рынка**:

- ✔ Несколько объявлений одного продавца на одной площадке
- ✔ Один продавец на разных площадках (разные названия)
- ✔ Разные продавцы в одной категории (похожий текст)
- ✔ Продавцы с одинаковыми брендами в ассортименте
- ✔ Продавцы с общим телефоном (если это один человек)
- ✔ Продавцы с похожими, но разными телефонами
- ✔ Объявления с украденными фото
- ✔ Объявления без контактов

### 2.3 Сложные случаи (обязательно включить)

| Случай | Описание | Ожидаемая сложность |
|--------|----------|---------------------|
| **Один продавец, разные названия** | «РемСервис» на Avito, «ИП Иванов» на Юле | Высокая |
| **Один телефон, разные адреса** | Передвижной сервис | Средняя |
| **Один адрес, разные телефоны** | Торговый центр — много продавцов | Высокая |
| **Одинаковые фото, разные продавцы** | Фото украдено из каталога | Средняя |
| **Шаблонный текст** | «Срочно! Дорого! Звоните!» у всех | Низкая (шум) |
| **Пустые контакты** | Только имя и город | Очень высокая |

---

## 3. Annotation Schema

### 3.1 Формат разметки для каждого Listing

```yaml
listing_id: "avito_001"
source: "avito"
url: "https://avito.ru/..."

# Основные поля
title: "Ремонт холодильников на дому"
category: "Услуги / Ремонт бытовой техники"
price: null                     # услуги без цены

# Контактная информация
seller_name: "Сергей"
phone: "+7 (999) 123-45-67"
email: null
address: "ул. Ленина, 10"
city: "Москва"

# Фото
photos:
  - hash: "sha256:a1b2c3..."
  - hash: "sha256:d4e5f6..."

# Разметчик
annotator: "human"
confidence: 1.0                # человеческая разметка = истина
notes: "Телефон совпадает с youla_014, адрес разный"
```

### 3.2 Поля для заполнения

| Поле | Обязательно | Формат |
|------|-------------|--------|
| listing_id | Да | `{source}_{id}` |
| source | Да | avito / youla / vk / telegram |
| url | Да | Полная ссылка |
| title | Да | Как в объявлении |
| category | Да | Двухуровневая |
| price | Да | Число или `null` |
| seller_name | Да | Как в объявлении |
| phone | Да | Строка или `null` |
| email | Да | Строка или `null` |
| address | Да | Строка или `null` |
| city | Да | Строка |
| photos | Да | Массив хешей или `[]` |
| notes | Нет | Комментарий разметчика |

---

## 4. Ground Truth

### 4.1 Seller Groups

Истинная принадлежность объявлений продавцам.

```yaml
ground_truth:
  seller_groups:
    
    - group_id: "SELLER_001"
      real_name: "ИП Иванов С.А."
      listings:
        - "avito_001"
        - "avito_014"
        - "youla_003"
        - "vk_007"
      notes: "Один продавец на 4 площадках. На Avito как 'Сергей', на Юле как 'ИП Иванов'."
    
    - group_id: "SELLER_002"
      real_name: "ООО «ТехноСервис»"
      listings:
        - "avito_005"
        - "youla_009"
      notes: "Юрлицо. На обеих площадках одинаковое название."
    
    - group_id: "SELLER_003"
      real_name: "Петров А.В. (частное лицо)"
      listings:
        - "avito_018"
      notes: "Только одно объявление. Продаёт личный ноутбук."
```

### 4.2 Edge Cases

```yaml
edge_cases:
  - case_id: "EC_001"
    description: "Два продавца с одинаковым адресом (торговый центр)"
    expected: "DIFFERENT_SELLERS"
    confidence: 0.95
    reason: "Разные телефоны, разные названия, общий адрес"
  
  - case_id: "EC_002"
    description: "Один продавец с двумя названиями"
    expected: "SAME_SELLER" 
    confidence: 0.85
    reason: "Один телефон, один адрес, похожие фото"
```

---

## 5. Match Analysis

### 5.1 Формат анализа пары

Для каждой возможной пары Listing → Listing записывается:

```yaml
pair_analysis:
  listing_a: "avito_001"
  listing_b: "youla_003"
  
  ground_truth: "SAME_SELLER"    # известный ответ
  
  # Сигналы
  signals:
    phone:
      match: true
      value_a: "+7 (999) 123-45-67"
      value_b: "+7 (999) 123-45-67"
      weight: 0.35
    
    address:
      match: false
      value_a: "ул. Ленина, 10"
      value_b: "пр. Мира, 5"
      weight: 0.00
    
    photo:
      match: true
      weight: 0.20
      detail: "2 из 5 фото совпадают"
  
  # Итог
  ai_confidence: null             # будет заполнено после прогона
  human_confidence: 0.92
  human_decision: "MATCH"
  human_notes: "Телефон + 2 фото. Адрес разный — может быть переезд."
```

### 5.2 Количество пар

При 50 объявлениях:
- Всего возможных пар: `C(50,2) = 1225`
- Анализировать все не нужно
- Достаточно: **~100 релевантных пар** (явные совпадения + сложные случаи)

---

## 6. Error Taxonomy

### 6.1 Категории ошибок

```yaml
errors:
  
  false_merge:
    code: "FM"
    description: "Разные продавцы объединены в одного"
    severity: "critical"
    impact: "Искажение карты рынка, потеря конкурентов"
    acceptable_rate: "< 1%"
  
  false_split:
    code: "FS"
    description: "Один продавец разделён на несколько"
    severity: "minor"
    impact: "Завышение числа продавцов, дубли"
    acceptable_rate: "< 15%"
  
  missing_evidence:
    code: "ME"
    description: "Система не обнаружила очевидную связь"
    severity: "medium"
    impact: "Недоверие к качеству системы"
    acceptable_rate: "< 10%"
  
  confidence_miscalibration:
    code: "CM"
    description: "AI уверен, но человек не согласен (или наоборот)"
    severity: "medium"
    impact: "Неправильные автоматические решения"
    acceptable_rate: "< 5%"
```

### 6.2 Матрица ошибок

| Реальность \ Решение AI | Match | No Match |
|-------------------------|-------|----------|
| **Same Seller** | True Positive ✅ | False Split ❌ |
| **Different Sellers** | False Merge ❌ | True Negative ✅ |

Приоритет: **False Merge rate должен быть 0% в первой итерации.**

---

## 7. Success Metrics

### 7.1 Целевые показатели

| Метрика | Цель | Минимум |
|---------|------|---------|
| **False Merge Rate** (FMR) | 0/50 | < 1% |
| **False Split Rate** (FSR) | < 3/50 | < 15% |
| **Precision** (TP / (TP+FP)) | > 95% | > 85% |
| **Recall** (TP / (TP+FN)) | > 80% | > 60% |
| **F1 Score** | > 0.87 | > 0.70 |
| **Evidence Coverage** | > 90% listings have ≥1 evidence | > 75% |

### 7.2 Калибровка Confidence

```yaml
calibration:
  target: "AI confidence должен совпадать с human confidence"
  
  acceptable_deviation: ±0.10    # в пределах 10% от человеческой оценки
  overconfidence_penalty: true   # AI уверен больше, чем прав — хуже, чем недооценка
  
  buckets:
    - range: [0.70, 0.80]
      expected_accuracy: 0.75
    - range: [0.80, 0.90]
      expected_accuracy: 0.85
    - range: [0.90, 1.00]
      expected_accuracy: 0.95
```

---

## 8. Golden Dataset Format

### 8.1 Структура файлов

```
golden_dataset_v1/
├── README.md                    # описание датасета
├── listings.json                # 50 объявлений с разметкой
├── entities.json                # ground truth seller groups
├── relationships.json           # эталонные связи
├── evidence.json                # извлечённые признаки
└── pairs.json                   # 100+ проанализированных пар
```

### 8.2 Форматы файлов

**listings.json**

```json
{
  "listings": [
    {
      "id": "avito_001",
      "source": "avito",
      "url": "https://...",
      "title": "Ремонт холодильников",
      "category": "Услуги / Ремонт",
      "price": null,
      "seller_name": "Сергей",
      "phone": "+7 (999) 123-45-67",
      "email": null,
      "address": "ул. Ленина, 10",
      "city": "Москва",
      "photos": ["sha256:a1b2c3..."],
      "annotator": "human",
      "notes": ""
    }
  ]
}
```

**entities.json**

```json
{
  "seller_groups": [
    {
      "id": "SELLER_001",
      "real_name": "ИП Иванов С.А.",
      "listings": ["avito_001", "avito_014", "youla_003"],
      "confidence": 1.0,
      "evidence": ["phone_match_001", "photo_match_003"],
      "notes": ""
    }
  ]
}
```

---

## 9. Human Review Process

### 9.1 Когда обязательна проверка

```yaml
review_rules:
  auto_approve:
    - confidence >= 0.90
    - AND min_independent_signals >= 3
    - AND no_contradictions: true
    
  auto_reject:
    - confidence < 0.40
    - OR only_one_signal: true
    
  requires_review:
    - confidence in [0.40, 0.90)
    - OR high_stakes: true       # дорогие товары / услуги
    - OR first_time_entity: true # новый продавец в системе
```

### 9.2 Процесс проверки

```yaml
review_process:
  step_1: "AI предлагает объединение с confidence score"
  step_2: "Система показывает Proof Chain (какие evidence)"
  step_3: "Человек подтверждает / отклоняет / уточняет"
  step_4: "Решение записывается в Audit Trail"
  step_5: "Если человек не согласен — система корректирует веса"
```

### 9.3 Роль человека

```
1st pass:    человек размечает 50 объявлений вручную (ground truth)
2nd pass:    AI предлагает свои объединения
3rd pass:    человек сравнивает AI vs ground truth
4th pass:    корректировка весов evidence на основе расхождений
5th pass:    повторный прогон AI с новыми весами
```

---

## 10. Experiment Protocol

### 10.1 Последовательность

```yaml
protocol:
  phase_1_collect:
    duration: "1 день"
    output: "50 объявлений сырых данных"
    
  phase_2_annotate:
    duration: "1–2 дня"
    output: "listings.json, entities.json"
  
  phase_3_analyze_pairs:
    duration: "1 день"
    output: "pairs.json, evidence.json"
  
  phase_4_ai_run:
    duration: "автоматически"
    output: "ai_predictions.json"
  
  phase_5_compare:
    duration: "1 день"
    output: "error_analysis.md"
  
  phase_6_adjust:
    duration: "1 день"
    output: "calibrated_weights.md"
  
  total: "~1 неделя"
```

### 10.2 Что делать с результатами

```yaml
if_false_merge_rate > 5%:
  action: "Откатить веса. Увеличить порог автоматического объединения."
  
if_false_split_rate > 20%:
  action: "Добавить новые match signals. Снизить порог."
  
if_evidence_coverage < 50%:
  action: "Улучшить извлечение evidence из raw данных."
  
if_all_metrics_good:
  action: "Перейти к Connector Framework с текущими весами."
```

---

## 11. Final Principle

> **Мы сначала учим систему понимать рынок, а потом масштабируем сбор данных.**

50 объявлений, размеченных вручную, ценнее 50 000 сырых записей без понимания, кто есть кто.

Золотой датасет — первый актив проекта. Он определяет, будет ли система умным анализатором или просто генератором шума.

---

## Приложение: Шаблоны для разметки

### A1. Чек-лист для каждого объявления

```markdown
- [ ] ID объявления записан
- [ ] URL работает
- [ ] Название скопировано полностью
- [ ] Категория определена
- [ ] Цена указана (или null)
- [ ] Телефон извлечён
- [ ] Email извлечён  
- [ ] Адрес записан
- [ ] Город указан
- [ ] Фото сосчитаны
- [ ] Комментарий добавлен
```

### A2. Чек-лист для парного сравнения

```markdown
- [ ] Телефон: совпадает / разный / нет данных
- [ ] Email: совпадает / разный / нет данных
- [ ] Адрес: совпадает / разный / нет данных
- [ ] Фото: совпадают / разные / нет данных
- [ ] Название: похоже / разное
- [ ] Категория: одинаковая / разная
- [ ] Итог: один продавец / разные продавцы / неопределено
- [ ] Уверенность: ___%
- [ ] Комментарий: _______________
```
