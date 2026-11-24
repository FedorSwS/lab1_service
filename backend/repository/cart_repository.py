import sqlite3
import json
import time
from typing import Optional, Dict, Any, List


class OptimisticLockError(Exception):
    pass


class CartRepository:
    """Слой доступа к данным (Repository Pattern + Optimistic Locking)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def find_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT id, sku, name, category, price_rub, stock_qty, version FROM products WHERE sku = ?",
            (sku,),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def list_products(self) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT id, sku, name, category, price_rub, stock_qty, version FROM products ORDER BY id"
        )
        return [dict(r) for r in cur.fetchall()]

    def insert_product(
        self, sku: str, name: str, category: str, price_rub: float, stock_qty: int
    ) -> Dict[str, Any]:
        cur = self.conn.execute(
            """
            INSERT INTO products(sku, name, category, price_rub, stock_qty, version)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (sku, name, category, price_rub, stock_qty),
        )
        self.conn.commit()
        return {
            "id": cur.lastrowid,
            "sku": sku,
            "name": name,
            "category": category,
            "price_rub": price_rub,
            "stock_qty": stock_qty,
            "version": 1,
        }

    def delete_product_by_sku(self, sku: str) -> int:
        row = self.find_product_by_sku(sku)
        if not row:
            return 0
        self.conn.execute("DELETE FROM cart_items WHERE product_id = ?", (row["id"],))
        cur = self.conn.execute("DELETE FROM products WHERE sku = ?", (sku,))
        self.conn.commit()
        return cur.rowcount

    def get_idempotent_response(self, idem_key: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.execute(
            "SELECT response_json FROM idempotency_keys WHERE idem_key = ?",
            (idem_key,),
        )
        row = cur.fetchone()
        return json.loads(row["response_json"]) if row else None

    def save_idempotent_response(self, idem_key: str, req_hash: str, resp: Dict[str, Any]) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO idempotency_keys(idem_key, request_hash, response_json, created_at) VALUES (?, ?, ?, ?)",
            (idem_key, req_hash, json.dumps(resp, ensure_ascii=False), int(time.time())),
        )

    def reserve_stock_optimistic(self, product_id: int, qty: int, expected_version: int) -> None:
        cur = self.conn.execute(
            """
            UPDATE products
               SET stock_qty = stock_qty - ?, version = version + 1
             WHERE id = ? AND version = ? AND stock_qty >= ?
            """,
            (qty, product_id, expected_version, qty),
        )
        if cur.rowcount == 0:
            raise OptimisticLockError(
                f"Конфликт версий или нехватка остатка для product_id={product_id}, version={expected_version}"
            )

    def upsert_cart_item(self, session_id: str, product_id: int, qty: int) -> int:
        cur = self.conn.execute(
            "INSERT INTO cart_items(session_id, product_id, qty, version) VALUES (?, ?, ?, 1)",
            (session_id, product_id, qty),
        )
        return cur.lastrowid

    def remove_cart_item(self, session_id: str, item_id: int) -> bool:
        row = self.conn.execute(
            "SELECT product_id, qty FROM cart_items WHERE id = ? AND session_id = ?",
            (item_id, session_id),
        ).fetchone()
        if not row:
            return False
        self.conn.execute(
            "UPDATE products SET stock_qty = stock_qty + ?, version = version + 1 WHERE id = ?",
            (row["qty"], row["product_id"]),
        )
        self.conn.execute(
            "DELETE FROM cart_items WHERE id = ? AND session_id = ?",
            (item_id, session_id),
        )
        self.conn.commit()
        return True

    def list_cart(self, session_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT c.id, c.qty, c.version, p.name, p.price_rub
              FROM cart_items c
              JOIN products p ON p.id = c.product_id
             WHERE c.session_id = ?
            """,
            (session_id,),
        )
        return [dict(r) for r in cur.fetchall()]
