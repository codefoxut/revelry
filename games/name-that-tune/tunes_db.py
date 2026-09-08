"""Shared SQLite access layer for the Name That Tune melody bank.

Same shape as emoji-charades/emoji_db.py (categories + items), except each
item is a public-domain melody: a title plus a note sequence (our own
hand-transcribed simplification of the tune, stored as JSON — not an audio
recording), so there's nothing here that needs licensing or attribution.
"""

import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "tunes.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    emoji TEXT NOT NULL,
    color TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tunes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id TEXT NOT NULL REFERENCES categories(id),
    title TEXT NOT NULL,
    notes_json TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tunes_unique ON tunes(category_id, title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_tunes_category ON tunes(category_id);
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


def _row_to_tune(row: sqlite3.Row) -> dict:
    return {"title": row["title"], "notes": json.loads(row["notes_json"])}


def random_tune(
    conn: sqlite3.Connection, category_id: str, exclude: list[str] | None = None
) -> dict | None:
    # Building "NOT IN (?, ?, ...)" only when exclude is non-empty avoids the
    # classic SQL pitfall where "NOT IN ()" evaluates to NULL/false for every
    # row and silently filters out everything.
    exclude_clause = (
        "AND title NOT IN ({}) COLLATE NOCASE".format(",".join("?" for _ in exclude))
        if exclude
        else ""
    )
    if category_id == "mixed":
        row = conn.execute(
            f"SELECT title, notes_json FROM tunes WHERE 1=1 {exclude_clause} ORDER BY RANDOM() LIMIT 1",
            (*(exclude or []),),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT title, notes_json FROM tunes WHERE category_id = ? {exclude_clause} ORDER BY RANDOM() LIMIT 1",
            (category_id, *(exclude or [])),
        ).fetchone()
    return _row_to_tune(row) if row else None


def tune_count(conn: sqlite3.Connection, category_id: str) -> int:
    if category_id == "mixed":
        row = conn.execute("SELECT COUNT(*) AS n FROM tunes").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM tunes WHERE category_id = ?", (category_id,)
        ).fetchone()
    return row["n"]


def add_category(conn: sqlite3.Connection, category_id: str, name: str, emoji: str, color: str, sort_order: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO categories (id, name, emoji, color, sort_order) VALUES (?, ?, ?, ?, ?)",
        (category_id, name, emoji, color, sort_order),
    )
    conn.commit()


def add_tunes(conn: sqlite3.Connection, category_id: str, tunes: list[tuple[str, list]]) -> int:
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO tunes (category_id, title, notes_json) VALUES (?, ?, ?)",
        [(category_id, title, json.dumps(notes)) for title, notes in tunes],
    )
    conn.commit()
    return conn.total_changes - before
