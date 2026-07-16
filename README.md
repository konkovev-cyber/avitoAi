# Market Agent 🤖

Персональный AI-агент поиска выгодных товаров и услуг на Авито и Юле.

## Архитектура

```
Telegram Bot / Dashboard
        ↓
   AI Search Agent
        ↓
   ┌────┴────┐
Avito       Yula
Collector   Collector
        ↓
  Raw Listings DB (SQLite)
        ↓
  AI Analyzer
        ↓
  Deal Score (0-100)
        ↓
  Telegram Alert
```

## Quick Start

```bash
# Клонировать
git clone https://github.com/konkovev-cyber/avitoAi.git
cd avitoAi

# Установить зависимости
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Настроить
cp .env.example .env
# вписать TELEGRAM_BOT_TOKEN

# Инициализировать БД
python3 main.py init

# Запустить
python3 main.py bot        # Telegram бот
python3 main.py collect    # Сборщик объявлений
python3 main.py dashboard  # Веб-дашборд
```

## Systemd Services

```bash
sudo systemctl start market-agent-bot
sudo systemctl start market-agent-collector
sudo systemctl start market-agent-dashboard
```

## Deal Scoring

Оценка сделки (0-100):

| Компонент | Вес | Описание |
|-----------|-----|----------|
| Ценовое преимущество | 50% | Насколько цена ниже рынка |
| Риски | -30% | Продавец, фото, описание |
| Качество | 20% | Полнота информации |

- **≥70** → 🔥 Немедленный алерт
- **≥50** → ✅ Стандартный алерт
- **<50** → Только в БД

## Структура

```
market_agent/
├── collector/      # Сборщики (Avito, Yula)
├── database/       # SQLite schema + CRUD
├── analyzer/       # Price model, Risk scorer, Deal engine
├── bot/            # Telegram Bot (premium inline UX)
├── dashboard/      # FastAPI + HTMX
├── models.py       # Pydantic модели
├── config.py       # Конфигурация
└── main.py         # CLI entry point
```

## License

MIT
