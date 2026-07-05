#!/usr/bin/env python3
"""One-time migration: data/categories.json -> data/categories.db.

Reads the final, fully-populated categories.json (see
tools/populate_categories.py) and loads it into a SQLite database using the
shared pictionary_db module, mirroring the bollywood-dumbcharades
movies.json -> movies.db migration.

Usage:
    python3 tools/migrate_json_to_db.py
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_PATH = BASE_DIR / "data" / "categories.json"

sys.path.insert(0, str(BASE_DIR))
import pictionary_db


def main():
    if not JSON_PATH.exists():
        print(f"{JSON_PATH} not found — nothing to migrate.")
        return

    with open(JSON_PATH) as f:
        data = json.load(f)

    if pictionary_db.DB_PATH and Path(pictionary_db.DB_PATH).exists():
        Path(pictionary_db.DB_PATH).unlink()

    conn = pictionary_db.get_connection()

    for sort_order, category in enumerate(data["categories"]):
        pictionary_db.add_category(
            conn,
            category["id"],
            category["name"],
            category["emoji"],
            category["color"],
            sort_order,
        )
        added = pictionary_db.add_items(conn, category["id"], category.get("items", []))
        total = pictionary_db.item_count(conn, category["id"])
        print(f"{category['id']}: {added} rows inserted -> {total} total items")

    conn.close()
    print(f"\nMigrated to {pictionary_db.DB_PATH}")


if __name__ == "__main__":
    main()
