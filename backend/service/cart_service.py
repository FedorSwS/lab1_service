import hashlib
import json
from typing import Dict, Any
from backend.repository.cart_repository import CartRepository, OptimisticLockError


class CartService:
    """Слой бизнес-логики: идемпотентность, оптимистические блокировки, расчёт суммы."""

    def __init__(self, repo: CartRepository):
        self.repo = repo

    def add_item(self, session_id: str, product_id: int, qty: int, expected_version: int, idem_key: str) -> Dict[str, Any]:
        cached = self.repo.get_idempotent_response(idem_key)
        if cached is not None:
            cached["idempotent_replay"] = True
            return cached

        payload_hash = hashlib.sha256(
            json.dumps({"s": session_id, "p": product_id, "q": qty}, sort_keys=True).encode()
        ).hexdigest()

        with self.repo.conn:
            self.repo.reserve_stock_optimistic(product_id, qty, expected_version)
            item_id = self.repo.upsert_cart_item(session_id, product_id, qty)
            resp = {"status": "ok", "cart_item_id": item_id, "idempotent_replay": False}
            self.repo.save_idempotent_response(idem_key, payload_hash, resp)
            return resp

    def remove_item(self, session_id: str, item_id: int) -> Dict[str, Any]:
        removed = self.repo.remove_cart_item(session_id, item_id)
        return {"deleted": removed, "cart_item_id": item_id}

    def get_cart_summary(self, session_id: str) -> Dict[str, Any]:
        items = self.repo.list_cart(session_id)
        total = round(sum(i["price_rub"] * i["qty"] for i in items), 2)
        return {"items": items, "total_rub": total}
