#!/usr/bin/env python3
"""Backfill hindi_title for existing data/movies.db rows where it's still
NULL (movies added before the hindi_title column existed), using Claude.

Usage:
    python3 tools/backfill_hindi_titles.py --limit 45
    python3 tools/backfill_hindi_titles.py --dry-run
    python3 tools/backfill_hindi_titles.py

Requires ANTHROPIC_API_KEY in the environment or a .env file (same as main.py).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import movie_db

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MAX_TOKENS_CEILING = 8000
BATCH_SIZE = 15

SYSTEM_PROMPT = """You are translating Bollywood/pan-India movie titles into \
Hindi for a dumb-charades party game database.

You will be given a list of REAL movie titles with their release years. Do \
not invent, rename, merge, or drop any titles — return exactly one JSON \
object per input title, in the same order given.

Each object must have exactly these fields:
- title (string): copy the input title back exactly as given
- hindi_title (string): a natural Hindi rendering of the title in \
Devanagari script (translation if the title has a clear Hindi meaning, \
otherwise a natural transliteration)

Output ONLY a JSON array of objects, nothing else — no markdown fences, no \
prose, no commentary."""


def translate_batch(batch: list[dict]) -> dict[str, str]:
    """Returns {movie_id: hindi_title} for one batch. Falls back to
    splitting the batch in half (and recursing) if the response comes back
    truncated or malformed.
    """
    if not batch:
        return {}

    max_tokens = min(MAX_TOKENS_CEILING, max(2048, len(batch) * 100 + 500))
    user_prompt = "Movies ({}):\n".format(len(batch)) + "\n".join(
        f"- title: \"{m['title']}\", year: {m['year']}" for m in batch
    )
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = message.content[0].text.strip()

    results = None
    if message.stop_reason != "max_tokens":
        try:
            parsed = json.loads(raw)
            if len(parsed) == len(batch):
                results = parsed
        except json.JSONDecodeError:
            pass

    if results is None:
        if len(batch) == 1:
            raise RuntimeError(
                f"Could not translate {batch[0]['title']!r} ({batch[0]['year']}) "
                "— response truncated or malformed"
            )
        mid = len(batch) // 2
        print(f"  response truncated/malformed for {len(batch)} movies, "
              f"splitting into {mid} + {len(batch) - mid} and retrying")
        return {**translate_batch(batch[:mid]), **translate_batch(batch[mid:])}

    return {
        original["id"]: entry["hindi_title"]
        for original, entry in zip(batch, results)
        if entry.get("hindi_title")
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, default=None,
                         help="cap how many rows get backfilled this run")
    parser.add_argument("--dry-run", action="store_true", help="print proposed translations without writing")
    args = parser.parse_args()

    missing = movie_db.movies_missing_hindi_title()
    print(f"{len(missing)} movies missing hindi_title")
    if args.limit:
        missing = missing[: args.limit]
        print(f"Processing {len(missing)} (--limit {args.limit})")

    if not missing:
        print("Nothing to backfill.")
        return

    all_translations: dict[str, str] = {}
    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        print(f"Translating batch {i // BATCH_SIZE + 1} ({len(batch)} movies) ...")
        all_translations.update(translate_batch(batch))

    if args.dry_run:
        print(json.dumps(all_translations, indent=2, ensure_ascii=False))
        print(f"\n[dry-run] Would update {len(all_translations)} rows. No rows written.")
        return

    updated = movie_db.update_hindi_titles(all_translations)
    print(f"Updated hindi_title for {updated} movies in {movie_db.DB_PATH}")


if __name__ == "__main__":
    main()
