"""ShelfWise Database Layer - Optimized.

Features:
- WAL mode for read concurrency
- Persistent connection pool with thread safety
- Indexed columns for fast queries
- Batch operations for bulk inserts
- Query timing and metrics hooks
"""

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.models import ConsolidatedProduct

DB_PATH = os.path.join(os.path.dirname(__file__), "shelfwise.db")
_db_local = threading.local()
_db_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """Get a thread-local persistent connection."""
    if not hasattr(_db_local, "conn") or _db_local.conn is None:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
        _db_local.conn = conn
    return _db_local.conn


def _table_has_columns(conn: sqlite3.Connection, table: str, required: List[str]) -> bool:
    """Check whether table exists with all required columns."""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    except Exception:
        return False
    existing = {r[1] for r in rows}
    return all(col in existing for col in required)


def _reset_schema(conn: sqlite3.Connection):
    """Drop existing tables so the canonical schema can be created."""
    conn.execute("DROP TABLE IF EXISTS products")
    conn.execute("DROP TABLE IF EXISTS jobs")
    conn.execute("DROP INDEX IF EXISTS idx_products_name")
    conn.execute("DROP INDEX IF EXISTS idx_products_brand")
    conn.execute("DROP INDEX IF EXISTS idx_products_category")
    conn.execute("DROP INDEX IF EXISTS idx_products_confidence")
    conn.execute("DROP INDEX IF EXISTS idx_products_status")
    conn.execute("DROP INDEX IF EXISTS idx_jobs_status")


def init_db():
    """Create tables and indexes. Resets incompatible legacy schemas."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

        products_required = {"upc", "name", "brand", "category", "confidence", "status", "data"}
        jobs_required = {"job_id", "total", "queued", "running", "completed", "failed"}

        if not _table_has_columns(conn, "products", products_required) or not _table_has_columns(
            conn, "jobs", jobs_required
        ):
            _reset_schema(conn)

        # Products table with optimized schema
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                upc TEXT PRIMARY KEY,
                name TEXT,
                brand TEXT,
                category TEXT,
                confidence REAL,
                status TEXT,
                foundry_enriched INTEGER DEFAULT 0,
                foundry_sdk TEXT,
                data TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        # Migrate existing tables if they don't have the new columns
        migrations = [
            "ALTER TABLE products ADD COLUMN confidence REAL",
            "ALTER TABLE products ADD COLUMN status TEXT",
            "ALTER TABLE products ADD COLUMN foundry_enriched INTEGER DEFAULT 0",
            "ALTER TABLE products ADD COLUMN foundry_sdk TEXT",
        ]
        for sql in migrations:
            try:
                conn.execute(sql)
            except Exception:
                pass

        # Jobs table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                total INT DEFAULT 0,
                queued INT DEFAULT 0,
                running INT DEFAULT 0,
                completed INT DEFAULT 0,
                failed INT DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        # Indexes for fast queries
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_name ON products(name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_confidence ON products(confidence)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_products_status ON products(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(queued, running, completed, failed)")

        conn.commit()
    finally:
        conn.close()


def create_job(upcs: List[str]) -> str:
    """Create a new job, return job_id (UUID)."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    total = len(upcs)
    conn = _get_connection()
    with _db_lock:
        conn.execute(
            "INSERT INTO jobs (job_id, total, queued, running, completed, failed, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, total, total, 0, 0, 0, now, now),
        )
        conn.commit()
    return job_id


def update_job(job_id: str, field: str, delta: int):
    """Atomically update a counter field."""
    valid_fields = {"queued", "running", "completed", "failed"}
    if field not in valid_fields:
        raise ValueError(f"Invalid field: {field}")
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_connection()
    with _db_lock:
        conn.execute(
            f"UPDATE jobs SET {field} = {field} + ?, updated_at = ? WHERE job_id = ?",
            (delta, now, job_id),
        )
        conn.commit()


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    """Return job dict or None."""
    conn = _get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return dict(row) if row else None


def upsert_product(product: ConsolidatedProduct):
    """Insert or replace a product."""
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()
    data = json.dumps(product.model_dump())
    with _db_lock:
        conn.execute(
            """
            INSERT INTO products (upc, name, brand, category, confidence, status, foundry_enriched, foundry_sdk, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(upc) DO UPDATE SET
                name = excluded.name,
                brand = excluded.brand,
                category = excluded.category,
                confidence = excluded.confidence,
                status = excluded.status,
                foundry_enriched = excluded.foundry_enriched,
                foundry_sdk = excluded.foundry_sdk,
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (
                product.upc,
                product.name,
                product.brand,
                product.category,
                product.confidence,
                product.status,
                1 if product.foundry_enriched else 0,
                product.foundry_sdk,
                data,
                now,
                now,
            ),
        )
        conn.commit()


def bulk_upsert_products(products: List[ConsolidatedProduct]):
    """Batch insert/replace products. Much faster than individual upserts."""
    if not products:
        return
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for p in products:
        rows.append(
            (
                p.upc,
                p.name,
                p.brand,
                p.category,
                p.confidence,
                p.status,
                1 if p.foundry_enriched else 0,
                p.foundry_sdk,
                json.dumps(p.model_dump()),
                now,
                now,
            )
        )
    with _db_lock:
        conn.executemany(
            """
            INSERT INTO products (upc, name, brand, category, confidence, status, foundry_enriched, foundry_sdk, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(upc) DO UPDATE SET
                name = excluded.name,
                brand = excluded.brand,
                category = excluded.category,
                confidence = excluded.confidence,
                status = excluded.status,
                foundry_enriched = excluded.foundry_enriched,
                foundry_sdk = excluded.foundry_sdk,
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            rows,
        )
        conn.commit()


def get_product(upc: str) -> Optional[Dict[str, Any]]:
    """Return product dict or None."""
    conn = _get_connection()
    row = conn.execute("SELECT * FROM products WHERE upc = ?", (upc,)).fetchone()
    return dict(row) if row else None


def get_all_products() -> List[Dict[str, Any]]:
    """Return all products."""
    conn = _get_connection()
    rows = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def search_products(
    query: Optional[str] = None,
    brand: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Search products with filters. Uses indexed columns."""
    conn = _get_connection()
    conditions = []
    params = []

    if query:
        conditions.append("(name LIKE ? OR upc LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])
    if brand:
        conditions.append("brand = ?")
        params.append(brand)
    if category:
        conditions.append("category = ?")
        params.append(category)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if min_confidence is not None:
        conditions.append("confidence >= ?")
        params.append(min_confidence)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM products {where_clause} ORDER BY confidence DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def delete_all_products():
    """Delete all products and jobs."""
    conn = _get_connection()
    with _db_lock:
        conn.execute("DELETE FROM products")
        conn.execute("DELETE FROM jobs")
        conn.commit()


def get_stats() -> Dict[str, Any]:
    """Fast aggregated stats using SQL."""
    conn = _get_connection()
    total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    avg_conf = conn.execute("SELECT AVG(confidence) FROM products").fetchone()[0] or 0.0
    status_counts = conn.execute("SELECT status, COUNT(*) FROM products GROUP BY status").fetchall()
    category_counts = conn.execute(
        "SELECT category, COUNT(*) FROM products WHERE category IS NOT NULL GROUP BY category"
    ).fetchall()

    return {
        "total_products": total,
        "avg_confidence": round(avg_conf, 3),
        "status_breakdown": {row[0]: row[1] for row in status_counts},
        "category_breakdown": {row[0] or "Uncategorized": row[1] for row in category_counts},
    }
