"""Shared SQLite access layer for the Emoji Charades puzzle bank.

Same shape as heads-up/heads_up_db.py and pictionary/pictionary_db.py
(categories + items) since Emoji Charades' offline fallback data is the
same kind of thing: a category with a pool of puzzles, here each item is an
(emoji, answer) pair instead of a bare word.
"""

import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "puzzles.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    emoji TEXT NOT NULL,
    color TEXT NOT NULL,
    sort_order INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS puzzles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id TEXT NOT NULL REFERENCES categories(id),
    clue TEXT NOT NULL,
    answer TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_puzzles_unique ON puzzles(category_id, answer COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_puzzles_category ON puzzles(category_id);
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


def random_puzzles(
    conn: sqlite3.Connection, category_id: str, n: int, exclude: list[str] | None = None
) -> list[dict]:
    # Building "NOT IN (?, ?, ...)" only when exclude is non-empty avoids the
    # classic SQL pitfall where "NOT IN ()" evaluates to NULL/false for every
    # row and silently filters out everything.
    exclude_clause = (
        "AND answer NOT IN ({}) COLLATE NOCASE".format(",".join("?" for _ in exclude))
        if exclude
        else ""
    )
    if category_id == "mixed":
        rows = conn.execute(
            f"SELECT clue, answer FROM puzzles WHERE 1=1 {exclude_clause} ORDER BY RANDOM() LIMIT ?",
            (*(exclude or []), n),
        ).fetchall()
    else:
        rows = conn.execute(
            f"SELECT clue, answer FROM puzzles WHERE category_id = ? {exclude_clause} ORDER BY RANDOM() LIMIT ?",
            (category_id, *(exclude or []), n),
        ).fetchall()
    return [{"clue": row["clue"], "answer": row["answer"]} for row in rows]


def puzzle_count(conn: sqlite3.Connection, category_id: str) -> int:
    if category_id == "mixed":
        row = conn.execute("SELECT COUNT(*) AS n FROM puzzles").fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM puzzles WHERE category_id = ?", (category_id,)
        ).fetchone()
    return row["n"]


def add_category(conn: sqlite3.Connection, category_id: str, name: str, emoji: str, color: str, sort_order: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO categories (id, name, emoji, color, sort_order) VALUES (?, ?, ?, ?, ?)",
        (category_id, name, emoji, color, sort_order),
    )
    conn.commit()


def add_puzzles(conn: sqlite3.Connection, category_id: str, puzzles: list[tuple[str, str]]) -> int:
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO puzzles (category_id, clue, answer) VALUES (?, ?, ?)",
        [(category_id, clue, answer) for clue, answer in puzzles],
    )
    conn.commit()
    return conn.total_changes - before
