#!/usr/bin/env python3
"""Backfill min_mime_seconds for existing data/movies.db rows that are
difficulty hard/ultra_hard but still NULL (rows curated before that field
existed), using Claude.

Usage:
    python3 tools/backfill_min_mime_seconds.py --limit 45
    python3 tools/backfill_min_mime_seconds.py --dry-run
    python3 tools/backfill_min_mime_seconds.py

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

SYSTEM_PROMPT = """You are estimating mime time for Bollywood/pan-India \
movie titles in a dumb-charades party game database.

You will be given a list of REAL movie titles, each already rated \
difficulty "hard" or "ultra_hard", with their release year and mime_hint \
(the gesture used to act it out). Do not invent, rename, merge, or drop \
any titles — return exactly one JSON object per input title, in the same \
order given.

Each object must have exactly these fields:
- title (string): copy the input title back exactly as given
- min_mime_seconds (int): minimum seconds realistically needed to mime \
this title out, given its mime_hint — longer/more abstract/multi-part \
mimes take more seconds; "ultra_hard" titles should generally need more \
seconds than "hard" ones

Output ONLY a JSON array of objects, nothing else — no markdown fences, no \
prose, no commentary."""


def _format_input_movie(m: dict) -> str:
    hint = m.get("mime_hint") or "(no hint recorded)"
    return f"- title: \"{m['title']}\", year: {m['year']}, difficulty: {m['difficulty']}, mime_hint: \"{hint}\""


def estimate_batch(batch: list[dict]) -> dict[str, int]:
    """Returns {movie_id: min_mime_seconds} for one batch. Falls back to
    splitting the batch in half (and recursing) if the response comes back
    truncated or malformed.
    """
    if not batch:
        return {}

    max_tokens = min(MAX_TOKENS_CEILING, max(2048, len(batch) * 100 + 500))
    user_prompt = "Movies ({}):\n".format(len(batch)) + "\n".join(
        _format_input_movie(m) for m in batch
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
                f"Could not estimate {batch[0]['title']!r} ({batch[0]['year']}) "
                "— response truncated or malformed"
            )
        mid = len(batch) // 2
        print(f"  response truncated/malformed for {len(batch)} movies, "
              f"splitting into {mid} + {len(batch) - mid} and retrying")
        return {**estimate_batch(batch[:mid]), **estimate_batch(batch[mid:])}

    return {
        original["id"]: int(entry["min_mime_seconds"])
        for original, entry in zip(batch, results)
        if entry.get("min_mime_seconds") is not None
    }


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, default=None,
                         help="cap how many rows get backfilled this run")
    parser.add_argument("--dry-run", action="store_true", help="print proposed estimates without writing")
    args = parser.parse_args()

    missing = movie_db.movies_missing_min_mime_seconds()
    print(f"{len(missing)} hard/ultra_hard movies missing min_mime_seconds")
    if args.limit:
        missing = missing[: args.limit]
        print(f"Processing {len(missing)} (--limit {args.limit})")

    if not missing:
        print("Nothing to backfill.")
        return

    all_estimates: dict[str, int] = {}
    for i in range(0, len(missing), BATCH_SIZE):
        batch = missing[i : i + BATCH_SIZE]
        print(f"Estimating batch {i // BATCH_SIZE + 1} ({len(batch)} movies) ...")
        all_estimates.update(estimate_batch(batch))

    if args.dry_run:
        print(json.dumps(all_estimates, indent=2, ensure_ascii=False))
        print(f"\n[dry-run] Would update {len(all_estimates)} rows. No rows written.")
        return

    updated = movie_db.update_min_mime_seconds(all_estimates)
    print(f"Updated min_mime_seconds for {updated} movies in {movie_db.DB_PATH}")


if __name__ == "__main__":
    main()
