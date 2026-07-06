#!/usr/bin/env python3
"""Pull real Bollywood/pan-India movie titles from IMDb's public
non-commercial datasets and curate them into the movie database
(data/movies.db) using Claude.

Unlike tools/scrape_wiki_movies.py (one Wikipedia year page per run), each
IMDb-sourced title already carries its own release year and, occasionally, a
real IMDb-contributed Hindi/Devanagari alternate title — so this script
curates titles across arbitrary years in one pass, ranked by IMDb vote count
(a proxy for "recognizable enough to guess from a mime").

IMDb's free datasets have no country-of-origin field, so
tools/sources/imdb_source.py's "original title in an Indian language" filter
is only a coarse candidate funnel — plenty of non-Indian films (e.g. Fight
Club, Interstellar) also pick up an "IN"/"hi" AKA from their Hindi dub and
pass it. Claude does the final call during curation via `is_bollywood`;
anything it marks false is dropped before insertion.

Usage:
    python3 tools/scrape_imdb_movies.py --min-votes 2000 --limit 30 --dry-run
    python3 tools/scrape_imdb_movies.py --min-votes 500

Requires ANTHROPIC_API_KEY in the environment or a .env file (same as main.py).
First run downloads ~700MB of IMDb dumps into tools/sources/.cache/ (cached
after that).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import movie_db
from sources import imdb_source

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MAX_TOKENS_CEILING = 16000
BATCH_SIZE = 15

# ---------------------------------------------------------------------------
# Movie Database Curation Prompt (IMDb variant — titles and years are real,
# hindi_title may already be supplied from a real IMDb AKA)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are curating a database of Bollywood (and pan-India \
Hindi-market) movies for a dumb-charades party game.

You will be given a list of movies sourced from IMDb, each with its title \
and release year. Some of these are NOT actually Indian productions — \
IMDb's dataset can't tell a real Bollywood/pan-India film from a foreign \
film (e.g. a Hollywood movie) that merely has a Hindi-dubbed alternate \
title on IMDb. You must make that call yourself using what you know about \
each film.

Do not invent, rename, merge, or drop any titles — return exactly one JSON \
object per input movie, in the same order given, so every input is \
accounted for (even the ones you mark as not Bollywood).

Each object must have exactly these fields:
- title (string): copy the input title back exactly as given
- year (int): copy the input year back exactly as given
- is_bollywood (bool): true only if this is a genuine Indian production \
(Hindi-original, or a pan-India hit in another Indian language widely \
watched via Hindi dub) — false for foreign (e.g. Hollywood) films that \
merely have an incidental Hindi-dub AKA on IMDb. When false, the remaining \
fields can be minimal filler; they will not be used.
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
Devanagari script. If the input already supplies a hindi_title, copy it \
back UNCHANGED (it comes from real IMDb data). Otherwise, produce your own \
best natural Hindi translation or transliteration of the title.

Mimeability criteria:
1. LENGTH DOESN'T MATTER — long or multi-word titles are fine; there's no \
"short/iconic" requirement.
2. CONCRETE — prefer a recognizable object, action, character, or scene \
over pure abstract wordplay; this affects difficulty, not inclusion.
3. RECOGNIZABLE — a mimed gesture should plausibly let a teammate guess \
it, eventually.
4. ULTRA_HARD — assign this tier (with a min_mime_seconds estimate) to \
titles that are long, abstract, wordplay-heavy, or otherwise take real \
effort/time to convey through mime. This replaces what used to be \
dumb_charades_ready = false.
5. If you don't recognize a title, make a reasonable guess from the words \
in it.

Output ONLY a JSON array of movie objects, nothing else — no markdown \
fences, no prose, no commentary."""


def _format_input_movie(m: dict) -> str:
    hindi_note = f", hindi_title: \"{m['hindi_title']}\"" if m.get("hindi_title") else ""
    return f"- title: \"{m['title']}\", year: {m['year']}{hindi_note}"


def curate_movies(candidates: list[dict]) -> list[dict]:
    """Curate every given candidate in a single Claude call. Falls back to
    splitting the batch in half (and recursing) only if the response comes
    back truncated or malformed.
    """
    if not candidates:
        return []

    max_tokens = min(MAX_TOKENS_CEILING, max(4096, len(candidates) * 200 + 1000))
    user_prompt = (
        f"Movies ({len(candidates)}):\n"
        + "\n".join(_format_input_movie(m) for m in candidates)
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
            if len(parsed) == len(candidates):
                results = parsed
        except json.JSONDecodeError:
            pass

    if results is None:
        if len(candidates) == 1:
            raise RuntimeError(
                f"Could not curate {candidates[0]['title']!r} ({candidates[0]['year']}) "
                "— response truncated or malformed"
            )
        mid = len(candidates) // 2
        print(f"  response truncated/malformed for {len(candidates)} movies, "
              f"splitting into {mid} + {len(candidates) - mid} and retrying")
        return curate_movies(candidates[:mid]) + curate_movies(candidates[mid:])

    normalized = []
    rejected = 0
    for original, entry in zip(candidates, results):
        if not entry.get("is_bollywood", False):
            rejected += 1
            continue
        entry["title"] = original["title"]  # trust our IMDb data over the model's echo
        entry["year"] = original["year"]
        if original.get("hindi_title"):
            entry["hindi_title"] = original["hindi_title"]
        normalized.append(movie_db.normalize(entry))
    if rejected:
        print(f"  dropped {rejected} title(s) Claude flagged as not actually Bollywood/Indian")
    return normalized


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--min-votes", type=int, default=500,
                         help="minimum IMDb vote count to consider a title (default 500)")
    parser.add_argument("--max-votes", type=int, default=20000,
                         help="maximum IMDb vote count to consider a title (default 20000; "
                              "pass 0 to disable — see tools/sources/imdb_source.py docstring "
                              "for why an unbounded top end skews toward non-Indian blockbusters)")
    parser.add_argument("--limit", type=int, default=None,
                         help="cap how many new candidates get sent for curation")
    parser.add_argument("--dry-run", action="store_true", help="print proposed additions without writing")
    args = parser.parse_args()

    max_votes = None if args.max_votes == 0 else args.max_votes
    print(f"Loading IMDb datasets (min_votes={args.min_votes}, max_votes={max_votes}) ...")
    candidates = imdb_source.bollywood_titles(min_votes=args.min_votes, max_votes=max_votes)
    print(f"Found {len(candidates)} candidate titles from IMDb")

    known = movie_db.existing_titles_lower()
    fresh = [m for m in candidates if m["title"].lower() not in known]
    skipped = len(candidates) - len(fresh)
    if args.limit:
        fresh = fresh[: args.limit]
    print(f"Skipping {skipped} already-known titles; curating {len(fresh)} new titles")

    if not fresh:
        print("Nothing new to curate.")
        return

    all_normalized = []
    for i in range(0, len(fresh), BATCH_SIZE):
        batch = fresh[i : i + BATCH_SIZE]
        print(f"Curating batch {i // BATCH_SIZE + 1} ({len(batch)} movies) ...")
        all_normalized.extend(curate_movies(batch))

    ready_count = sum(1 for m in all_normalized if m["dumb_charades_ready"])
    hindi_count = sum(1 for m in all_normalized if m.get("hindi_title"))

    if args.dry_run:
        print(json.dumps(all_normalized, indent=2, ensure_ascii=False))
        print(f"\n[dry-run] Would add {len(all_normalized)} movies "
              f"({ready_count} dumb-charades-ready, {hindi_count} with hindi_title). No rows written.")
        return

    added = movie_db.insert_movies(all_normalized)
    print(f"Added {added} movies ({ready_count} dumb-charades-ready, {hindi_count} with hindi_title) "
          f"to {movie_db.DB_PATH}")


if __name__ == "__main__":
    main()
