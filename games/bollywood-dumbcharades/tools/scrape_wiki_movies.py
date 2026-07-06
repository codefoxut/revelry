#!/usr/bin/env python3
"""Scrape Wikipedia's "List of Hindi films of <year>" and curate the
results into the movie database (data/movies.db) using Claude.

Usage:
    python3 tools/scrape_wiki_movies.py --year 2023
    python3 tools/scrape_wiki_movies.py --year 2023 --limit 15 --dry-run

Requires ANTHROPIC_API_KEY in the environment or a .env file (same as main.py).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

import anthropic
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import movie_db

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

WIKI_URL_TEMPLATE = "https://en.wikipedia.org/wiki/List_of_Hindi_films_of_{year}"
USER_AGENT = "BollywoodDumbCharadesBot/1.0 (educational hobby project; local use)"
MAX_TOKENS_CEILING = 16000
JUNK_TITLES = {"", "tba", "n/a", "-"}

# ---------------------------------------------------------------------------
# Movie Database Curation Prompt (scrape variant — titles are real, not invented)
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are curating a database of Bollywood (and pan-India \
Hindi-market) movies for a dumb-charades party game.

You will be given a list of REAL movie titles scraped from Wikipedia for a \
known release year. Do not invent, rename, merge, or drop any titles — \
return exactly one JSON object per input title, in the same order given.

Each object must have exactly these fields:
- title (string): copy the input title back exactly as given
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


def fetch_page(year: int) -> str:
    url = WIKI_URL_TEMPLATE.format(year=year)
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.text


def clean_title(text: str) -> str:
    # strip trailing footnote/citation markers like "[γ]" or "[15]"
    return re.sub(r"\[[^\]]*\]\s*$", "", text).strip()


def is_release_table(headers: list[str]) -> bool:
    has_title = any("title" in h or h == "film" for h in headers)
    has_credit_column = any(h in ("director", "cast", "opening") for h in headers)
    return has_title and has_credit_column


def expand_header_row(header_row) -> list[str]:
    """Expand a header <tr> into one lowercase name per physical column.

    A header cell's `colspan` (e.g. a merged "Opening" header covering
    separate Month/Day sub-columns) makes the header count undercount the
    real column count if left un-expanded, which throws off every row's
    column alignment below it.
    """
    headers: list[str] = []
    for cell in header_row.find_all(["th", "td"]):
        colspan = int(cell.get("colspan", 1) or 1)
        headers.extend([cell.get_text(strip=True).lower()] * colspan)
    return headers


def build_row_grid(row, num_cols: int, pending: dict) -> list[Optional[str]]:
    """Reconstruct one data row into a `num_cols`-wide grid of cell text.

    Cells carried down by a `rowspan` from an earlier row are re-inserted at
    their original column via `pending` (column index -> (text, rows left)),
    so a row missing a leading grouped column (e.g. a rowspan'd release
    month/quarter) still lines up under the right header. Any of the row's
    own cells beyond `num_cols` (stray/malformed trailing cells) are simply
    not placed anywhere, rather than shifting real columns out of position.
    """
    grid: list[Optional[str]] = [None] * num_cols
    cells = iter(row.find_all(["td", "th"]))
    current = next(cells, None)
    col = 0
    while col < num_cols:
        if col in pending:
            text, remaining = pending[col]
            grid[col] = text
            if remaining > 1:
                pending[col] = (text, remaining - 1)
            else:
                del pending[col]
            col += 1
            continue
        if current is None:
            break
        text = current.get_text(strip=True)
        rowspan = int(current.get("rowspan", 1) or 1)
        colspan = int(current.get("colspan", 1) or 1)
        for c in range(colspan):
            if col + c >= num_cols:
                break
            grid[col + c] = text
            if rowspan > 1:
                pending[col + c] = (text, rowspan - 1)
        col += colspan
        current = next(cells, None)
    return grid


def extract_titles(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    titles: list[str] = []
    seen_lower: set[str] = set()

    for table in soup.select("table.wikitable"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = expand_header_row(rows[0])
        if not is_release_table(headers):
            continue
        title_idx = next((i for i, h in enumerate(headers) if "title" in h or h == "film"), None)
        if title_idx is None:
            continue

        pending: dict = {}
        for row in rows[1:]:
            if not row.find_all(["td", "th"]):
                continue
            grid = build_row_grid(row, len(headers), pending)
            if grid[title_idx] is None:
                continue
            title = clean_title(grid[title_idx])
            if title.lower() in JUNK_TITLES or title.lower() in seen_lower:
                continue
            seen_lower.add(title.lower())
            titles.append(title)

    return titles


def curate_titles(titles: list[str], year: int) -> list[dict]:
    """Curate every given title in a single Claude call. Falls back to
    splitting the batch in half (and recursing) only if the response comes
    back truncated or malformed — so a normal year's worth of titles goes to
    Claude in one shot, and splitting is the exception, not the rule.
    """
    if not titles:
        return []

    max_tokens = min(MAX_TOKENS_CEILING, max(4096, len(titles) * 200 + 1000))
    user_prompt = (
        f"Release year: {year}\n"
        f"Titles ({len(titles)}):\n" + "\n".join(f"- {t}" for t in titles)
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
            if len(parsed) == len(titles):
                results = parsed
        except json.JSONDecodeError:
            pass

    if results is None:
        if len(titles) == 1:
            raise RuntimeError(
                f"Could not curate title {titles[0]!r} for {year} — response truncated or malformed"
            )
        mid = len(titles) // 2
        print(f"  [{year}] response truncated/malformed for {len(titles)} titles, "
              f"splitting into {mid} + {len(titles) - mid} and retrying")
        return curate_titles(titles[:mid], year) + curate_titles(titles[mid:], year)

    normalized = []
    for original_title, entry in zip(titles, results):
        entry["title"] = original_title  # trust our scrape over the model's echo
        normalized.append(movie_db.normalize(entry, force_year=year))
    return normalized


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True, help="release year to scan, e.g. 2023")
    parser.add_argument("--limit", type=int, default=None, help="cap the number of scraped titles processed")
    parser.add_argument("--dry-run", action="store_true", help="print proposed additions without writing")
    args = parser.parse_args()

    print(f"Fetching {WIKI_URL_TEMPLATE.format(year=args.year)} ...")
    html = fetch_page(args.year)

    scraped = extract_titles(html)
    print(f"Scraped {len(scraped)} unique titles for {args.year}")

    known = movie_db.existing_titles_lower()
    fresh = [t for t in scraped if t.lower() not in known]
    skipped = len(scraped) - len(fresh)
    if args.limit:
        fresh = fresh[: args.limit]
    print(f"Skipping {skipped} already-known titles; curating {len(fresh)} new titles")

    if not fresh:
        print("Nothing new to curate.")
        return

    all_normalized = curate_titles(fresh, args.year)

    ready_count = sum(1 for m in all_normalized if m["dumb_charades_ready"])

    if args.dry_run:
        print(json.dumps(all_normalized, indent=2))
        print(f"\n[dry-run] Would add {len(all_normalized)} movies ({ready_count} dumb-charades-ready). No rows written.")
        return

    added = movie_db.insert_movies(all_normalized)
    print(f"Added {added} movies ({ready_count} dumb-charades-ready) to {movie_db.DB_PATH}")


if __name__ == "__main__":
    main()
