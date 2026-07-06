"""Shared SQLite access for the Bollywood movie database.

Used by main.py (read-only, for game sessions) and the tools/ scripts
(read + write, for growing the database).
"""

import re
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "movies.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS movies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER NOT NULL,
    decade TEXT NOT NULL,
    genres TEXT NOT NULL,
    language TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    dumb_charades_ready INTEGER NOT NULL,
    mime_hint TEXT,
    tags TEXT NOT NULL,
    franchise TEXT,
    hindi_title TEXT,
    min_mime_seconds INTEGER
);
CREATE INDEX IF NOT EXISTS idx_movies_ready ON movies(dumb_charades_ready);
CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> sqlite3.Connection:
    conn = get_connection()
    conn.executescript(SCHEMA)
    for statement in (
        "ALTER TABLE movies ADD COLUMN hindi_title TEXT",
        "ALTER TABLE movies ADD COLUMN min_mime_seconds INTEGER",
    ):
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "year": row["year"],
        "decade": row["decade"],
        "genres": row["genres"].split(",") if row["genres"] else [],
        "language": row["language"],
        "difficulty": row["difficulty"],
        "dumb_charades_ready": bool(row["dumb_charades_ready"]),
        "mime_hint": row["mime_hint"],
        "tags": row["tags"].split(",") if row["tags"] else [],
        "franchise": row["franchise"],
        "hindi_title": row["hindi_title"],
        "min_mime_seconds": row["min_mime_seconds"],
    }


def all_movies() -> list[dict]:
    conn = init_db()
    rows = conn.execute("SELECT * FROM movies ORDER BY year").fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def ready_movies() -> list[dict]:
    conn = init_db()
    rows = conn.execute(
        "SELECT * FROM movies WHERE dumb_charades_ready = 1 ORDER BY year"
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def existing_ids() -> set[str]:
    conn = init_db()
    ids = {row[0] for row in conn.execute("SELECT id FROM movies")}
    conn.close()
    return ids


def existing_titles_lower() -> set[str]:
    conn = init_db()
    titles = {row[0].lower() for row in conn.execute("SELECT title FROM movies")}
    conn.close()
    return titles


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


def normalize(entry: dict, force_year: int | None = None) -> dict:
    """Normalize a Claude-curated entry (or a hand-authored one) into a DB row."""
    year = force_year if force_year is not None else entry["year"]
    decade = f"{(year // 10) * 10}s"
    return {
        "id": slugify(entry["title"]),
        "title": entry["title"],
        "year": year,
        "decade": decade,
        "genres": entry.get("genres", []),
        "language": entry.get("language", "Hindi"),
        "difficulty": entry.get("difficulty", "medium"),
        "dumb_charades_ready": bool(entry.get("dumb_charades_ready", False)),
        "mime_hint": entry.get("mime_hint"),
        "tags": entry.get("tags", []),
        "franchise": entry.get("franchise"),
        "hindi_title": entry.get("hindi_title"),
        "min_mime_seconds": entry.get("min_mime_seconds"),
    }


def insert_movies(movies: list[dict]) -> int:
    """Insert normalized movie dicts, skipping any whose id already exists.

    Returns the number of rows actually inserted.
    """
    conn = init_db()
    added = 0
    for m in movies:
        try:
            conn.execute(
                """
                INSERT INTO movies
                    (id, title, year, decade, genres, language, difficulty,
                     dumb_charades_ready, mime_hint, tags, franchise, hindi_title,
                     min_mime_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    m["id"],
                    m["title"],
                    m["year"],
                    m["decade"],
                    ",".join(m["genres"]),
                    m["language"],
                    m["difficulty"],
                    int(m["dumb_charades_ready"]),
                    m["mime_hint"],
                    ",".join(m["tags"]),
                    m["franchise"],
                    m.get("hindi_title"),
                    m.get("min_mime_seconds"),
                ),
            )
            added += 1
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()
    return added


def movies_missing_hindi_title() -> list[dict]:
    conn = init_db()
    rows = conn.execute(
        "SELECT * FROM movies WHERE hindi_title IS NULL ORDER BY year"
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def update_hindi_titles(mapping: dict[str, str]) -> int:
    """Set hindi_title for existing rows by id. Returns rows updated."""
    conn = init_db()
    updated = 0
    for movie_id, hindi_title in mapping.items():
        cur = conn.execute(
            "UPDATE movies SET hindi_title = ? WHERE id = ?", (hindi_title, movie_id)
        )
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated


def movies_missing_min_mime_seconds() -> list[dict]:
    """Rows that should have a min_mime_seconds estimate (difficulty
    hard/ultra_hard) but don't yet — e.g. rows curated before that field
    existed."""
    conn = init_db()
    rows = conn.execute(
        "SELECT * FROM movies WHERE difficulty IN ('hard', 'ultra_hard') "
        "AND min_mime_seconds IS NULL ORDER BY year"
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]


def update_min_mime_seconds(mapping: dict[str, int]) -> int:
    """Set min_mime_seconds for existing rows by id. Returns rows updated."""
    conn = init_db()
    updated = 0
    for movie_id, seconds in mapping.items():
        cur = conn.execute(
            "UPDATE movies SET min_mime_seconds = ? WHERE id = ?", (seconds, movie_id)
        )
        updated += cur.rowcount
    conn.commit()
    conn.close()
    return updated
