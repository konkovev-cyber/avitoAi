# Connector Specification — Market Intelligence OS v1.0

> *Любой Connector возвращает только Listing + Evidence. Всё остальное — задача ядра.*

---

## 1. Contract

### 1.1 Обязательства Connector

Connector **обязан** вернуть:

```yaml
connector_output:
  listings: List[Listing]    # нормализованные объявления
  evidence: List[Evidence]   # извлечённые доказательства
```

Connector **не имеет права** возвращать:

```yaml
forbidden:
  - Seller          # задача Entity Resolution
  - Company         # задача Entity Resolution
  - Match           # задача Entity Resolution
  - Confidence      # задача Entity Resolution
  - Relationship    # задача Market Graph
```

### 1.2 Единственный метод

```python
class BaseConnector(ABC):
    async def search(self, query: SearchQuery) -> ConnectorResult:
        """Вернуть Listing + Evidence. Ничего больше."""
        ...

    async def health(self) -> ConnectorHealth:
        """Может ли коннектор сейчас работать."""
        ...

    def capabilities(self) -> ConnectorCapabilities:
        """Какие поля коннектор умеет извлекать."""
        ...

    def limitations(self) -> ConnectorLimitations:
        """Какие данные принципиально недоступны."""
        ...
```

---

## 2. Listing — единая модель данных

Любой источник → единый `Listing`. Ядро не знает, откуда пришли данные.

```yaml
Listing:
  # Обязательные поля
  id: str                    # source_listing_{hash}
  source: str                # avito | yandex_maps | yandex_market | ozon | wildberries | company_website
  url: str                   # прямая ссылка на источник
  title: str                 # название объявления/карточки
  category: str              # двухуровневая: "Ремонт бытовой техники / Ремонт холодильников"
  collection_date: str       # ISO 8601

  # Опциональные, но желательные поля
  description: str | None
  price: float | None
  currency: str              # "RUB"
  seller_name: str | None    # как указано на площадке

  # Контакты (извлекаются, если доступны)
  contacts:
    phone: str | None
    email: str | None
    website: str | None
    telegram: str | None
    vk: str | None

  # Локация
  location:
    city: str | None
    address: str | None
    coordinates: dict | None  # {lat, lng}

  # Медиа
  images: list[str]          # URL или хеши
  rating: float | None
  reviews_count: int | None
  working_hours: str | None

  # Метаданные коннектора
  raw_data: dict             # полный оригинальный ответ источника (для traceability)
  connector_version: str
```

### 2.1 Покрытие полей по источникам

```yaml
field_coverage_matrix:
  phone:
    yandex_maps: false       # скрыт, нужен клик по карточке
    company_website: true    # почти всегда есть
    avito: sometimes         # часто скрыт за кнопкой
    yandex_market: false     # не показывается
    ozon: false              # не показывается
    wildberries: false       # не показывается

  website:
    yandex_maps: sometimes   # если указан на карточке
    company_website: true
    avito: rarely
    yandex_market: false
    ozon: false

  email:
    yandex_maps: false
    company_website: sometimes
    avito: false
    marketplace: false

  inn:
    yandex_maps: false
    company_website: sometimes
    marketplace: false
```

---

## 3. Evidence — доказательства из Connector

Connector извлекает evidence **из своего источника**. Не строит гипотезы, не объединяет.

```yaml
Evidence:
  id: str                    # source_{type}_{hash}
  type: str                  # phone_extracted | email_extracted | address_extracted |
                             # website_extracted | photo_hash | inn_extracted | ogrn_extracted |
                             # name_extracted | category_extracted | working_hours
  source_listing: str        # ID listing, откуда извлечено
  value: str                 # значение признака
  field: str                 # поле в listing, откуда взято (contacts.phone, location.address...)
  confidence: float          # насколько коннектор уверен в правильности извлечения
  extraction_method: str     # rule_based | ai | html_parse | api_field
  collection_date: str       # ISO 8601
```

### 3.1 Что извлекать

```yaml
extraction_rules:
  phone:
    method: regex            # \+7[\d\s\-\(\)]{7,15}
    confidence: 0.95         # если найден — почти всегда корректен
  
  email:
    method: regex            # [\w\.\-]+@[\w\.\-]+\.\w+
    confidence: 0.90
  
  inn:
    method: regex            # \b\d{10}\b | \b\d{12}\b
    confidence: 0.98         # если соответствует формату — почти всегда ИНН
  
  website:
    method: regex + dns      # проверка существования домена
    confidence: 0.85
  
  photo_hash:
    method: perceptual_hash  # phash для сравнения
    confidence: 0.80
```

---

## 4. Connector Metadata

### 4.1 Health

```yaml
ConnectorHealth:
  status: str                # healthy | degraded | down
  last_success: str          # ISO 8601
  error: str | None
  response_time_ms: int
```

### 4.2 Capabilities

```yaml
ConnectorCapabilities:
  fields: list[str]          # ["title", "price", "phone", "address", ...]
  search_modes: list[str]    # ["by_query", "by_category", "by_url"]
  rate_limit: str            # "10/min"
  requires_proxy: bool
```

### 4.3 Limitations

```yaml
ConnectorLimitations:
  never_available: list[str]     # поля, которых не будет никогда
    - example: yandex_market → ["phone", "email", "inn"]
  sometimes_available: list[str] # поля, которые могут быть
    - example: avito → ["phone"]
  legal_restrictions: list[str]  # юридические ограничения
    - example: "Avito TOS запрещает автоматический сбор"
```

---

## 5. Регистрация Connector

```python
# connectors/registry.py

class ConnectorRegistry:
    def __init__(self):
        self._connectors: dict[str, BaseConnector] = {}
    
    def register(self, name: str, connector: BaseConnector):
        self._connectors[name] = connector
    
    def get(self, name: str) -> BaseConnector:
        return self._connectors[name]
    
    def list_available(self) -> list[ConnectorCapabilities]:
        return [c.capabilities() for c in self._connectors.values()]
    
    def search_all(self, query: SearchQuery) -> list[ConnectorResult]:
        """Запустить поиск по всем зарегистрированным коннекторам."""
```

---

## 6. Первый Connector: Яндекс Карты

```yaml
connector: yandex_maps
priority: 1

available_fields:
  - title
  - category
  - seller_name
  - location.address
  - location.city
  - rating
  - reviews_count
  - working_hours
  - contacts.website (sometimes)

never_available:
  - contacts.phone         # скрыт в выдаче
  - contacts.email         # не показывается
  - inn                    # не показывается

extraction_strategy:
  type: webfetch + parse
  rate_limit: "30/min"
  proxy: required (при большом объёме)
```

### 6.1 Реализация

```python
# connectors/yandex_maps_connector.py

class YandexMapsConnector(BaseConnector):
    async def search(self, query: SearchQuery) -> ConnectorResult:
        url = self._build_url(query)
        html = await self._fetch(url)
        items = self._parse_items(html)
        
        listings = []
        evidence = []
        
        for item in items:
            listing = self._to_listing(item)
            ev = self._extract_evidence(item, listing.id)
            listings.append(listing)
            evidence.extend(ev)
        
        return ConnectorResult(listings=listings, evidence=evidence)
```

---

## 7. Критерий готовности SDK

SDK считается готовым, если:

1. Можно написать новый коннектор, не меняя ядро.
2. Регистрация коннектора — одна строка.
3. Все коннекторы возвращают `Listing + Evidence`.
4. Ядро не знает имя источника.

---

## 8. Roadmap Connector'ов

```yaml
connector_roadmap:
  phase_2_1:
    - yandex_maps        # уже есть данные, понятная структура
    - company_website    # хорошо дополняет карты
  
  phase_2_2:
    - avito              # сложнее (CAPTCHA, прокси)
    - youla              # неофициальное API
  
  phase_2_3:
    - yandex_market      # commerce модель
    - ozon               # commerce модель
  
  phase_2_4:
    - wildberries        # commerce модель
    - telegram           # социальные источники
    - vk                 # социальные источники
```

---

## 9. Final Principle

> **Connector не знает, что такое Seller. Connector возвращает Listing + Evidence. Всё остальное — задача ядра.**

Эта граница защищает систему от耦合 с источниками данных и позволяет добавлять новые площадки без изменения бизнес-логики.
