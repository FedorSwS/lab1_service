# Лабораторная работа №1: Основы технологии AJAX (Корзина товаров «Bloom Shop»)

## Архитектура (4 слоя)
1. **Presentation Layer (`frontend/`)**: `index.html`, `js/ajaxClient.js`, `css/styles.css` — кроссбраузерный `XMLHttpRequest` + `jQuery` клиент с генерацией `Idempotency-Key` и защитой от двойных кликов.
2. **Application / Service Layer (`backend/service/cart_service.py`)**: бизнес-логика корзины, проверка остатков, кэш ключей идемпотентности (TTL), обработка конфликтов оптимистической блокировки (`version`).
3. **Data Access Layer (`backend/repository/cart_repository.py`)**: параметризованные SQL-запросы (Prepared Statements), оптимистическая блокировка (`UPDATE ... WHERE id=? AND version=?`).
4. **Database Layer (`db/schema.sql`, SQLite/MySQL)**: таблицы `products`, `cart_items`, `idempotency_keys`.

## Запуск
```bash
python3 backend/server.py
python3 tests/load_test.py
```
