#!/usr/bin/env python3
"""HTTP-сервер презентационного/контроллерного уровня для AJAX-корзины."""
import json
import os
import sqlite3
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.repository.cart_repository import CartRepository, OptimisticLockError
from backend.service.cart_service import CartService

DB_PATH = ROOT / "db" / "bloom_cart.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    conn.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    if count == 0:
        conn.executemany(
            "INSERT INTO products(sku, name, category, price_rub, stock_qty, version) VALUES (?,?,?,?,?,1)",
            [
                ("BLM-0001", "Розы классика", "Букеты", 2500, 12),
                ("BLM-0002", "Тюльпаны", "Букеты", 1800, 15),
                ("BLM-0003", "Пионы", "Букеты", 3200, 8),
            ],
        )
        conn.commit()
    conn.close()


class AjaxHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/products":
            conn = _connect()
            items = CartRepository(conn).list_products()
            conn.close()
            self._send_json(200, {"items": items, "count": len(items)})
            return
        if parsed.path == "/api/products/check":
            sku = parse_qs(parsed.query).get("sku", [""])[0]
            conn = _connect()
            prod = CartRepository(conn).find_product_by_sku(sku)
            conn.close()
            self._send_json(200, {"available": bool(prod and prod["stock_qty"] > 0), **(prod or {})})
            return
        if parsed.path == "/api/cart":
            conn = _connect()
            summary = CartService(CartRepository(conn)).get_cart_summary("demo-session")
            conn.close()
            self._send_json(200, summary)
            return
        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/products":
            body = self._read_json()
            conn = _connect()
            try:
                prod = CartRepository(conn).insert_product(
                    body["sku"],
                    body["name"],
                    body.get("category", "Букеты"),
                    float(body["price_rub"]),
                    int(body.get("stock_qty", 0)),
                )
                self._send_json(201, prod)
            except sqlite3.IntegrityError:
                self._send_json(409, {"error": "SKU уже существует"})
            finally:
                conn.close()
            return
        if parsed.path == "/api/cart/add":
            body = self._read_json()
            idem_key = self.headers.get("Idempotency-Key", "missing-key")
            conn = _connect()
            try:
                res = CartService(CartRepository(conn)).add_item(
                    "demo-session", body["product_id"], body["qty"], body["expected_version"], idem_key
                )
                self._send_json(200, res)
            except OptimisticLockError as exc:
                self._send_json(409, {"error": str(exc)})
            finally:
                conn.close()
            return
        self._send_json(404, {"error": "Not found"})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        prefix = "/api/cart/item/"
        if parsed.path.startswith(prefix):
            item_id = int(parsed.path[len(prefix):])
            conn = _connect()
            res = CartService(CartRepository(conn)).remove_item("demo-session", item_id)
            conn.close()
            self._send_json(200 if res["deleted"] else 404, res)
            return
        if parsed.path == "/api/products":
            sku = parse_qs(parsed.query).get("sku", [""])[0]
            conn = _connect()
            deleted = CartRepository(conn).delete_product_by_sku(sku)
            conn.close()
            if deleted:
                self._send_json(200, {"deleted": True, "sku": sku})
            else:
                self._send_json(404, {"error": "Товар не найден", "sku": sku})
            return
        self._send_json(404, {"error": "Not found"})

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, code: int, payload: dict):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    os.chdir(ROOT)
    _init_db()
    print("AJAX server ready on http://127.0.0.1:8081")
    HTTPServer(("127.0.0.1", 8081), AjaxHandler).serve_forever()
