"""Shared SQLite access layer for the Pictionary category data.

Backs the offline fallback path in server.py plus the static-population
tools (tools/populate_categories.py, tools/update_categories.py). Online
card generation (Claude) is untouched — this module only replaces the old
categories.json blob as the offline data store.
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
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


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


def random_items(conn: sqlite3.Connection, category_id: str, n: int) -> list[str]:
    rows = conn.execute(
        "SELECT text FROM items WHERE category_id = ? ORDER BY RANDOM() LIMIT ?",
        (category_id, n),
    ).fetchall()
    return [row["text"] for row in rows]


def sample_items_for_prompt(conn: sqlite3.Connection, category_id: str, limit: int = 50) -> list[str]:
    rows = conn.execute(
        "SELECT text FROM items WHERE category_id = ? ORDER BY RANDOM() LIMIT ?",
        (category_id, limit),
    ).fetchall()
    return [row["text"] for row in rows]


def add_items(conn: sqlite3.Connection, category_id: str, items: list[str]) -> int:
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO items (category_id, text) VALUES (?, ?)",
        [(category_id, item) for item in items],
    )
    conn.commit()
    return conn.total_changes - before


def item_count(conn: sqlite3.Connection, category_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM items WHERE category_id = ?", (category_id,)
    ).fetchone()
    return row["n"]


def add_category(conn: sqlite3.Connection, category_id: str, name: str, emoji: str, color: str, sort_order: int) -> None:
    conn.execute(
        "INSERT INTO categories (id, name, emoji, color, sort_order) VALUES (?, ?, ?, ?, ?)",
        (category_id, name, emoji, color, sort_order),
    )
    conn.commit()
