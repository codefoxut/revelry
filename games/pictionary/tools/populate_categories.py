#!/usr/bin/env python3
"""Bulk-populate data/categories.db from real, static, offline data
sources — no Claude/LLM calls, no per-item cost.

Each category pulls from one or more public datasets/APIs (see
tools/sources/): WordNet lexical trees, GeoNames' city dump, IMDb's public
title datasets, O*NET's occupation database, and Wikipedia's category
graph. Two categories (sports, fantasy) have a genuinely small real-world
domain — a few hundred to low thousands of distinct real items — and
cannot reach a 10,000-item target without fabricating entries, so this
script reports their actual ceiling honestly instead of padding.

Usage:
    python3 tools/populate_categories.py                    # all categories, target 10000
    python3 tools/populate_categories.py --category animals
    python3 tools/populate_categories.py --target 5000 --dry-run
    python3 tools/populate_categories.py --rebuild-cache     # force re-download sources

Downloaded source files are cached under tools/sources/.cache/ so re-runs
don't re-fetch large public dumps every time.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(__file__).resolve().parent / "sources" / ".cache"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(BASE_DIR))

import pictionary_db
from sources import geonames_source, imdb_source, onet_source, wikipedia_category_source, wordnet_source

MAX_ITEM_LENGTH = 60

SOURCES = {
    "objects": [
        lambda: wordnet_source.hyponym_lemmas("artifact.n.01"),
    ],
    "professions": [
        lambda: onet_source.profession_titles(),
    ],
    "places": [
        lambda: geonames_source.place_names(),
    ],
    "movies": [
        lambda: imdb_source.movie_titles(min_votes=1000),
    ],
    "animals": [
        lambda: wordnet_source.hyponym_lemmas("animal.n.01"),
        lambda: wikipedia_category_source.crawl_category(
            "Animals", max_depth=3, max_pages=20000, max_categories=2000, max_seconds=150, verbose=True
        ),
    ],
    "food": [
        lambda: wordnet_source.hyponym_lemmas("food.n.01", "food.n.02"),
        lambda: wikipedia_category_source.crawl_category(
            "Food and drink", max_depth=3, max_pages=20000, max_categories=2000, max_seconds=150, verbose=True
        ),
    ],
    "nature": [
        lambda: wordnet_source.hyponym_lemmas(
            "natural_object.n.01", "geological_formation.n.01", "plant.n.02"
        ),
    ],
    "actions": [
        lambda: wordnet_source.all_verb_lemmas(),
    ],
    "sports": [
        lambda: wordnet_source.hyponym_lemmas("sport.n.01"),
        lambda: wikipedia_category_source.crawl_category(
            "Sports", max_depth=2, max_pages=5000, max_categories=1000, max_seconds=90, verbose=True
        ),
    ],
    "fantasy": [
        lambda: wikipedia_category_source.crawl_category(
            "Legendary creatures", max_depth=2, max_pages=5000, max_categories=1000, max_seconds=90, verbose=True
        ),
    ],
}

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_and_dedupe(candidates: list[str], seen_lower: set[str]) -> list[str]:
    """Clean up raw candidate strings and drop anything already added
    earlier in this same batch (case-insensitively). Cross-category and
    cross-run dedup against existing DB rows is handled by the unique
    index at insert time.
    """
    results = []
    for raw in candidates:
        cleaned = _WHITESPACE_RE.sub(" ", raw).strip()
        if not cleaned or not cleaned.isprintable():
            continue
        if len(cleaned) > MAX_ITEM_LENGTH:
            continue
        lowered = cleaned.lower()
        if lowered in seen_lower:
            continue
        seen_lower.add(lowered)
        results.append(cleaned)
    return results


def populate_category(conn, category_id: str, target: int, dry_run: bool) -> None:
    sources = SOURCES.get(category_id)
    if not sources:
        print(f"{category_id}: no sources configured, skipping")
        return

    before_count = pictionary_db.item_count(conn, category_id)
    seen_lower = set()

    fresh = []
    for source_fn in sources:
        try:
            candidates = source_fn()
        except Exception as exc:
            print(f"  {category_id}: source failed ({exc!r}), skipping this source")
            continue
        added = normalize_and_dedupe(candidates, seen_lower)
        print(f"  {category_id}: source yielded {len(candidates)} raw -> {len(added)} new unique")
        fresh.extend(added)
        if before_count + len(fresh) >= target:
            break

    fresh = fresh[: max(0, target - before_count)] if before_count < target else []

    if dry_run:
        after_count = before_count + len(fresh)
        print(f"{category_id}: {before_count} -> {after_count} (target {target}) [dry-run estimate]")
    else:
        pictionary_db.add_items(conn, category_id, fresh)
        after_count = pictionary_db.item_count(conn, category_id)
        print(f"{category_id}: {before_count} -> {after_count} (target {target})")

    if after_count < target:
        print(f"  ⚠ short of target by {target - after_count} — real-world domain exhausted for this category's sources")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--category", help="only populate this category id (default: all categories)")
    parser.add_argument("--target", type=int, default=10000, help="target item count per category (default 10000)")
    parser.add_argument("--dry-run", action="store_true", help="print proposed additions without writing")
    parser.add_argument("--rebuild-cache", action="store_true", help="delete cached source downloads and re-fetch")
    args = parser.parse_args()

    if args.rebuild_cache and CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        print(f"Cleared {CACHE_DIR}")

    conn = pictionary_db.get_connection()

    targets = [c["id"] for c in pictionary_db.list_categories(conn)]
    if args.category:
        targets = [cid for cid in targets if cid == args.category]
        if not targets:
            parser.error(f"category id '{args.category}' not found")

    for category_id in targets:
        populate_category(conn, category_id, args.target, args.dry_run)

    if args.dry_run:
        print("\n[dry-run] No changes written.")
    else:
        print(f"\nWrote updated counts to {pictionary_db.DB_PATH}")

    conn.close()


if __name__ == "__main__":
    main()
