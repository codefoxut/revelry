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
- difficulty (string): "easy" | "medium" | "hard" — how hard the title is \
to guess once mimed
- dumb_charades_ready (bool): true ONLY if the title is genuinely mimeable
- mime_hint (string or null): one short phrase suggesting how to act it \
out, required whenever dumb_charades_ready is true, otherwise null
- tags (array of lowercase strings): free-form flavor tags (actor, \
franchise, era, cult status)
- franchise (string or null): franchise/series name if part of one

Mimeability criteria for dumb_charades_ready = true:
1. SHORT OR ICONIC — a title/phrase a mimer can gesture in under a minute.
2. CONCRETE — has a recognizable object, action, character, or scene \
rather than being purely abstract wordplay.
3. RECOGNIZABLE — a mimed gesture would plausibly let a teammate guess it.
4. If you don't recognize a title, make a reasonable guess from the words \
in it and default dumb_charades_ready to false when unsure.

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


def extract_titles(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    titles: list[str] = []
    seen_lower: set[str] = set()

    for table in soup.select("table.wikitable"):
        rows = table.find_all("tr")
        if not rows:
            continue
        headers = [h.get_text(strip=True).lower() for h in rows[0].find_all(["th", "td"])]
        if not is_release_table(headers):
            continue
        title_idx = next((i for i, h in enumerate(headers) if "title" in h or h == "film"), None)
        if title_idx is None:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if not cells:
                continue
            offset = len(headers) - len(cells)
            idx = title_idx - offset
            if not (0 <= idx < len(cells)):
                continue
            title = clean_title(cells[idx].get_text(strip=True))
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
