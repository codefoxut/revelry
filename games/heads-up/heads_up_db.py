"""Shared SQLite access layer for the Heads Up! word bank.

Same shape as pictionary/pictionary_db.py (categories + items), reused here
because Heads Up's offline fallback data is the same kind of thing: a
category with a pool of short guessable terms.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "categories.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    emoji TEXT NOT NULL,
    color TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id TEXT NOT NULL REFERENCES categories(id),
    text TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_items_unique ON items(category_id, text COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def is_empty(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()
    return row["n"] == 0


def list_categories(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, name, emoji, color FROM categories ORDER BY sort_order"
    ).fetchall()
    return [dict(row) for row in rows]


def get_category(conn: sqlite3.Connection, category_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, name, emoji, color FROM categories WHERE id = ?", (category_id,)
    ).fetchone()
    return dict(row) if row else None


def random_items(conn: sqlite3.Connection, category_id: str, n: int, exclude: list[str] | None = None) -> list[str]:
    # Building "NOT IN (?, ?, ...)" only when exclude is non-empty avoids the
    # classic SQL pitfall where "NOT IN ()" (or NOT IN with a NULL literal)
    # evaluates to NULL/false for every row and silently filters out everything.
    exclude_clause = "AND text NOT IN ({}) COLLATE NOCASE".format(",".join("?" for _ in exclude)) if exclude else ""
    if category_id == "mixed":
        rows = conn.execute(
            f"SELECT text FROM items WHERE 1=1 {exclude_clause} ORDER BY RANDOM() LIMIT ?",
            (*(exclude or []), n),
        ).fetchall()
        return [row["text"] for row in rows]
    rows = conn.execute(
        f"SELECT text FROM items WHERE category_id = ? {exclude_clause} ORDER BY RANDOM() LIMIT ?",
        (category_id, *(exclude or []), n),
    ).fetchall()
    return [row["text"] for row in rows]


def item_count(conn: sqlite3.Connection, category_id: str) -> int:
    if category_id == "mixed":
        row = conn.execute("SELECT COUNT(*) AS n FROM items").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM items WHERE category_id = ?", (category_id,)
        ).fetchone()
    return row["n"]


def add_category(conn: sqlite3.Connection, category_id: str, name: str, emoji: str, color: str, sort_order: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO categories (id, name, emoji, color, sort_order) VALUES (?, ?, ?, ?, ?)",
        (category_id, name, emoji, color, sort_order),
    )
    conn.commit()


def add_items(conn: sqlite3.Connection, category_id: str, items: list[str]) -> int:
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO items (category_id, text) VALUES (?, ?)",
        [(category_id, item) for item in items],
    )
    conn.commit()
    return conn.total_changes - before
