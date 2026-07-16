# Golden Dataset v1 — Sprint 001

## Market Segment
Ремонт бытовой техники (ремонт холодильников, стиральных машин)

## Structure
```
golden_dataset_v1/
├── raw/           # Исходные данные по источникам
├── normalized/    # Приведённые к единому формату Listing
├── annotations/   # Человеческая разметка (ground truth)
├── evidence/      # Извлечённые доказательства
└── reports/       # Аналитика спринта
```

## Sources (7)
| Источник | Модель | Кол-во | Статус |
|----------|--------|--------|--------|
| Avito | Service | 15 | ⏳ сбор |
| Яндекс Карты | Service | 10 | 🟡 5 собрано |
| Юла | Service | 5 | ⏳ |
| Сайты компаний | Service | 5 | ⏳ |
| Ozon | Commerce | 5 | ⏳ |
| Яндекс Маркет | Commerce | 5 | ⏳ |
| Wildberries | Commerce | 5 | ⏳ |

## Sprint Goal
Доказать, что Intelligence Model умеет восстанавливать реальных продавцов из разрозненных источников.

## Status
📅 Sprint 001 started — data collection in progress
