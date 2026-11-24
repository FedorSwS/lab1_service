-- Схема БД для AJAX-корзины «Bloom Shop» (совместима с MySQL 8 / SQLite 3)
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(128) NOT NULL,
    category VARCHAR(64) NOT NULL,
    price_rub DECIMAL(10,2) NOT NULL,
    stock_qty INTEGER NOT NULL DEFAULT 0,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) NOT NULL,
    product_id INTEGER NOT NULL,
    qty INTEGER NOT NULL CHECK(qty > 0),
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    idem_key VARCHAR(64) PRIMARY KEY,
    request_hash VARCHAR(64) NOT NULL,
    response_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
CREATE INDEX IF NOT EXISTS idx_cart_session ON cart_items(session_id);
