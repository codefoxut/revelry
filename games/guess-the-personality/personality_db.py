"""Shared SQLite access for the personality database.

Used by main.py (read-only, for sampling a game's secret personality pool)
and tools/scrape_wikidata_personalities.py (read + write, for growing the
database from Wikidata).
"""

import random
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "personalities.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS personalities (
    id TEXT PRIMARY KEY,
    wikidata_qid TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_indian INTEGER NOT NULL,
    nationality TEXT,
    occupation TEXT,
    gender TEXT,
    birth_year INTEGER,
    death_year INTEGER,
    description TEXT,
    sitelinks INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_personalities_is_indian ON personalities(is_indian);
CREATE INDEX IF NOT EXISTS idx_personalities_sitelinks ON personalities(sitelinks);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> sqlite3.Connection:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "wikidata_qid": row["wikidata_qid"],
        "name": row["name"],
        "is_indian": bool(row["is_indian"]),
        "nationality": row["nationality"],
        "occupation": row["occupation"],
        "gender": row["gender"],
        "birth_year": row["birth_year"],
        "death_year": row["death_year"],
        "description": row["description"],
        "sitelinks": row["sitelinks"],
    }


def count(category: str = "world") -> int:
    """category: 'world' (everyone) or 'india' (is_indian = 1)."""
    conn = init_db()
    if category == "india":
        row = conn.execute("SELECT COUNT(*) FROM personalities WHERE is_indian = 1").fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM personalities").fetchone()
    conn.close()
    return row[0]


def sample_personalities(category: str, n: int, pool_multiplier: int = 20) -> list[dict]:
    """Randomly sample n personalities for the given category, biased toward
    higher sitelinks (more recognizable) by drawing from the top
    n * pool_multiplier rows by sitelinks rather than uniformly across the
    full long tail."""
    conn = init_db()
    where = "WHERE is_indian = 1" if category == "india" else ""
    pool_size = max(n * pool_multiplier, n)
    rows = conn.execute(
        f"SELECT * FROM personalities {where} ORDER BY sitelinks DESC LIMIT ?",
        (pool_size,),
    ).fetchall()
    conn.close()
    people = [_row_to_dict(r) for r in rows]
    if len(people) <= n:
        return people
    return random.sample(people, n)


def existing_qids() -> set[str]:
    conn = init_db()
    qids = {row[0] for row in conn.execute("SELECT wikidata_qid FROM personalities")}
    conn.close()
    return qids


def slug_id(qid: str) -> str:
    return "q" + qid.lstrip("Qq")


def insert_personalities(people: list[dict]) -> int:
    """Insert normalized personality dicts, skipping any whose
    wikidata_qid already exists. Returns the number of rows actually
    inserted."""
    conn = init_db()
    added = 0
    for p in people:
        try:
            conn.execute(
                """
                INSERT INTO personalities
                    (id, wikidata_qid, name, is_indian, nationality, occupation,
                     gender, birth_year, death_year, description, sitelinks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    slug_id(p["wikidata_qid"]),
                    p["wikidata_qid"],
                    p["name"],
                    int(p["is_indian"]),
                    p.get("nationality"),
                    p.get("occupation"),
                    p.get("gender"),
                    p.get("birth_year"),
                    p.get("death_year"),
                    p.get("description"),
                    p.get("sitelinks", 0),
                ),
            )
            added += 1
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()
    return added
