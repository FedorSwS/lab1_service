#!/usr/bin/env python3
"""Функциональные и нагрузочные тесты (2 000 000 записей) для ЛР №1 (AJAX)."""
import sys, time, sqlite3, tempfile, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.repository.cart_repository import CartRepository, OptimisticLockError
from backend.service.cart_service import CartService


def run_benchmark(total_rows: int = 2_000_000):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Path(tmp) / "lab1.db"
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=OFF;")
            conn.executescript(
                (Path(__file__).resolve().parent.parent / "db/schema.sql").read_text(encoding="utf-8")
            )

            t0 = time.perf_counter()
            batch = 50_000
            for start in range(0, total_rows, batch):
                rows = [(f"BLM-{i:07d}", f"Букет #{i}", "Букеты", 2500.0 + (i % 500), 100, 1)
                        for i in range(start, min(start + batch, total_rows))]
                conn.executemany(
                    "INSERT INTO products(sku, name, category, price_rub, stock_qty, version) VALUES (?,?,?,?,?,?)",
                    rows,
                )
                conn.commit()
            insert_sec = time.perf_counter() - t0

            repo = CartRepository(conn)
            svc = CartService(repo)

            r1 = svc.add_item("sess-1", 1, 2, 1, "idem-test-001")
            r2 = svc.add_item("sess-1", 1, 2, 1, "idem-test-001")
            assert r1["idempotent_replay"] is False and r2["idempotent_replay"] is True
            conflict_caught = False
            try:
                svc.add_item("sess-2", 1, 1, 1, "idem-test-002") 
            except OptimisticLockError:
                conflict_caught = True
            assert conflict_caught

            
            latencies_ms = []
            for idx in range(0, total_rows, total_rows // 2000):
                s = time.perf_counter()
                p = repo.find_product_by_sku(f"BLM-{idx:07d}")
                assert p is not None
                latencies_ms.append((time.perf_counter() - s) * 1000.0)

            latencies_ms.sort()
            return {
                "total_rows": total_rows,
                "bulk_insert_sec": round(insert_sec, 2),
                "insert_rows_per_sec": int(total_rows / insert_sec),
                "lookup_p50_ms": round(statistics.median(latencies_ms), 4),
                "lookup_p95_ms": round(latencies_ms[int(len(latencies_ms) * 0.95)], 4),
                "lookup_p99_ms": round(latencies_ms[int(len(latencies_ms) * 0.99)], 4),
                "idempotency_passed": True,
                "optimistic_lock_passed": conflict_caught,
            }
        finally:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.close()


if __name__ == "__main__":
    print(run_benchmark())
