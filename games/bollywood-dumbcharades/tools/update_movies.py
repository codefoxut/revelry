#!/usr/bin/env python3
"""Grow/refresh the movie database (data/movies.db) using Claude.

Usage:
    python3 tools/update_movies.py --count 20
    python3 tools/update_movies.py --count 10 --focus "2020s Bollywood" --dry-run

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

# ---------------------------------------------------------------------------
# Movie Database Curation Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are curating a database of Bollywood (and pan-India \
Hindi-market) movies for a dumb-charades party game.

Each entry must be a JSON object with exactly these fields:
- title (string): the official movie title
- year (int): theatrical release year
- genres (array of lowercase strings): e.g. ["action", "drama"]
- language (string): "Hindi" for Hindi-original films, or the original \
language (e.g. "Telugu") for pan-India hits widely watched in Hindi-dub
- difficulty (string): "easy" | "medium" | "hard" | "ultra_hard" — how hard \
the title is to guess once mimed
- dumb_charades_ready (bool): true if there is any concrete mimeable \
anchor at all; false only for a title where no gesture is possible \
whatsoever (rare)
- mime_hint (string or null): one short phrase suggesting how to act it \
out, required whenever dumb_charades_ready is true, otherwise null
- min_mime_seconds (int or null): minimum seconds realistically needed to \
mime this out — REQUIRED (non-null) when difficulty is "hard" or \
"ultra_hard", otherwise null
- tags (array of lowercase strings): free-form flavor tags (actor, \
franchise, era, cult status)
- franchise (string or null): franchise/series name if part of one
- hindi_title (string): a natural Hindi rendering of the title in \
Devanagari script

Mimeability criteria:
1. LENGTH DOESN'T MATTER — long or multi-word titles are fine; there's no \
"short/iconic" requirement.
2. CONCRETE — prefer a recognizable object, action, character, or scene \
(a sword, a wrestling move, a moon, a train) over pure abstract wordplay; \
this affects difficulty, not inclusion.
3. RECOGNIZABLE — a mimed gesture should plausibly let a teammate guess \
it, eventually.
4. ULTRA_HARD — assign this tier (with a min_mime_seconds estimate) to \
titles that are long, abstract, wordplay-heavy, or otherwise take real \
effort/time to convey through mime (e.g. "Kuch Kuch Hota Hai"). This \
replaces what used to be dumb_charades_ready = false.

Output ONLY a JSON array of movie objects, nothing else — no markdown \
fences, no prose, no commentary."""


def build_user_prompt(existing_titles: list[str], count: int, focus: str | None) -> str:
    focus_line = f"\nFocus area for this batch: {focus}\n" if focus else ""
    return (
        f"Generate exactly {count} NEW Bollywood movie entries for the "
        f"database below.{focus_line}\n"
        "Do not repeat any of these already-catalogued titles:\n"
        + "\n".join(f"- {t}" for t in existing_titles)
    )


def request_movies(existing_titles: list[str], count: int, focus: str | None) -> list[dict]:
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(existing_titles, count, focus)}],
    )
    raw = message.content[0].text.strip()
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=20, help="how many new movies to request")
    parser.add_argument("--focus", type=str, default=None, help="optional steer, e.g. '2020s Bollywood'")
    parser.add_argument("--dry-run", action="store_true", help="print proposed additions without writing")
    args = parser.parse_args()

    existing_ids = movie_db.existing_ids()
    existing_titles_lower = movie_db.existing_titles_lower()
    existing_titles = [m["title"] for m in movie_db.all_movies()]

    proposed = request_movies(existing_titles, args.count, args.focus)

    normalized = []
    for entry in proposed:
        if "title" not in entry or "year" not in entry:
            continue
        n = movie_db.normalize(entry)
        if n["id"] in existing_ids or n["title"].lower() in existing_titles_lower:
            continue
        existing_ids.add(n["id"])
        existing_titles_lower.add(n["title"].lower())
        normalized.append(n)

    ready_count = sum(1 for m in normalized if m["dumb_charades_ready"])

    if args.dry_run:
        print(json.dumps(normalized, indent=2))
        print(f"\n[dry-run] Would add {len(normalized)} movies ({ready_count} dumb-charades-ready). No rows written.")
        return

    added = movie_db.insert_movies(normalized)
    print(f"Added {added} movies ({ready_count} dumb-charades-ready) to {movie_db.DB_PATH}")


if __name__ == "__main__":
    main()
