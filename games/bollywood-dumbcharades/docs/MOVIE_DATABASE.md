# Movie database

This app draws its dumb-charades movie list from `data/movies.db` (SQLite)
instead of letting the LLM invent titles from memory each game. This file
exists so any LLM (or human) picking up this project later can extend the
data correctly without needing prior conversation context.

## Why a database at all

Letting the host LLM freely pick movie titles each turn is unpredictable:
titles vary run-to-run, there's no control over which are actually easy to
mime, and it depends on the LLM behaving well every single turn. A curated,
queryable list fixes that — `main.py` samples from it and the LLM only
hosts/narrates.

SQLite (not a JSON file) is the storage format: it stays compact and
indexed as the list scales into the hundreds/thousands, instead of growing
into an ever-larger pretty-printed text file.

## Schema

`data/movies.db`, single table `movies`:

| Column                 | Type    | Notes                                                                 |
|------------------------|---------|------------------------------------------------------------------------|
| `id`                   | TEXT PK | lowercase hyphen slug of `title`, unique, used for dedup                |
| `title`                | TEXT    | official movie title                                                    |
| `hindi_title`          | TEXT \| NULL | Hindi/Devanagari rendering of `title` — a real IMDb alternate title when one exists, otherwise an LLM translation/transliteration; `NULL` until backfilled — see [`tools/backfill_hindi_titles.py`](#4-backfill-existing-rows--toolsbackfill_hindi_titlespy) |
| `year`                 | INTEGER | theatrical release year                                                 |
| `decade`               | TEXT    | derived from `year`, formatted `"1990s"`, `"2000s"`, etc.               |
| `genres`               | TEXT    | comma-separated lowercase, e.g. `"action,drama"`                        |
| `language`             | TEXT    | `"Hindi"` for Hindi-original films; original language (e.g. `"Telugu"`) for pan-India hits watched in Hindi dub |
| `difficulty`           | TEXT    | `"easy" \| "medium" \| "hard" \| "ultra_hard"` — how hard to guess once mimed; `ultra_hard` is the "takes real effort" tier (see criteria below) — nothing is excluded from play based on this |
| `dumb_charades_ready`  | INTEGER | `0`/`1` — legacy column, kept for compatibility but **no longer used to filter which movies get played** (that logic used to live in `main.py`/`movie_db.ready_movies()`); near-always `1` now that "hard to mime" is expressed via `difficulty = "ultra_hard"` instead of exclusion |
| `mime_hint`            | TEXT \| NULL | one short phrase suggesting how to act it out; set when `dumb_charades_ready = 1`, otherwise `NULL` |
| `min_mime_seconds`     | INTEGER \| NULL | minimum seconds realistically needed to mime the title; set only when `difficulty` is `"hard"` or `"ultra_hard"`, otherwise `NULL` |
| `tags`                 | TEXT    | comma-separated: franchise, actor, cult status, era                     |
| `franchise`            | TEXT \| NULL | franchise/series name if part of one, else `NULL`                 |

Indexed on `dumb_charades_ready` and `year` (the ready index is a leftover
from when that column gated queries — harmless, just no longer load-bearing).

All access goes through `movie_db.py` (project root) — `main.py` and all
`tools/` scripts import it rather than touching SQLite directly. Key
functions: `all_movies()`, `ready_movies()` (legacy, unused by `main.py`),
`existing_ids()`, `existing_titles_lower()`, `movies_missing_hindi_title()`,
`update_hindi_titles(mapping)`, `movies_missing_min_mime_seconds()`,
`update_min_mime_seconds(mapping)`, `slugify(title)`, `normalize(entry,
force_year=None)`, `insert_movies(list[dict]) -> int`.

## Difficulty & mimeability criteria

1. **Length doesn't matter** — long or multi-word titles are fine; there's
   no "short/iconic" requirement.
2. **Concrete** — prefer a recognizable object, action, character, or scene
   (a sword, a wrestling move, a moon, a train) over pure abstract
   wordplay. This affects `difficulty`, not whether a title is included.
3. **Recognizable** — a mimed gesture should plausibly let a teammate guess
   it, eventually.
4. **`ultra_hard`** — assign this tier (with a `min_mime_seconds` estimate)
   to titles that are long, abstract, wordplay-heavy, or otherwise take
   real effort/time to convey through mime (e.g. *Kuch Kuch Hota Hai*).
   This replaces what used to be `dumb_charades_ready = false` — every
   title stays in the playable pool regardless of difficulty.

## Extending the database

Three ways to grow it — all write through `movie_db.py`, so `id` slugs,
dedup rules, and schema stay consistent. Prefer these over touching SQLite
by hand.

### 1. Free-form curation — `tools/update_movies.py`

Asks Claude to invent new, real Bollywood titles matching the schema.

```bash
python3 tools/update_movies.py --count 20
python3 tools/update_movies.py --count 10 --focus "2020s Bollywood" --dry-run
```

- `--count N` — how many new movies to request (default 20)
- `--focus TEXT` — optional steer, e.g. an era or theme
- `--dry-run` — print proposed additions without writing

### 2. Scrape a real year from Wikipedia — `tools/scrape_wiki_movies.py`

Fetches `https://en.wikipedia.org/wiki/List_of_Hindi_films_of_<year>`,
extracts the real release-calendar titles for that year, then asks Claude
to fill in the schema fields for those *exact* titles (it's told not to
invent, rename, or drop any).

```bash
python3 tools/scrape_wiki_movies.py --year 2023
python3 tools/scrape_wiki_movies.py --year 2023 --limit 15 --dry-run
```

- `--year YYYY` — required, which year's Wikipedia list to scan
- `--limit N` — cap how many scraped titles get sent for curation (useful
  for a quick/cheap test run)
- `--dry-run` — print proposed additions without writing

Titles already in the database (case-insensitive title match) are skipped
before curation to avoid redundant API calls. Curation happens in batches
of 15 titles per Claude call.

### 3. Pull real movies from IMDb — `tools/scrape_imdb_movies.py`

Downloads IMDb's public non-commercial dataset dumps (`title.basics`,
`title.ratings`, `title.akas` — cached under `tools/sources/.cache/` after
the first run, ~700MB total), filters to titles released in India
(`title.akas` `region == "IN"`) ranked by vote count (a proxy for
"recognizable enough to guess from a mime"), then curates them into the
schema the same way as the Wikipedia path. Unlike that path, each title
already carries its own real release year, so a single run can span
arbitrary years. `tools/sources/imdb_source.py` also opportunistically
captures a genuine Devanagari-script IMDb alternate title per movie where
one exists, passed through to curation as a pre-filled `hindi_title` (the
model is told to copy it back unchanged rather than re-translate it).

```bash
python3 tools/scrape_imdb_movies.py --min-votes 2000 --limit 30 --dry-run
python3 tools/scrape_imdb_movies.py --min-votes 500
```

- `--min-votes N` — minimum IMDb vote count to consider a title (default 500)
- `--limit N` — cap how many new candidates get sent for curation
- `--dry-run` — print proposed additions without writing

### 4. Backfill existing rows — `tools/backfill_hindi_titles.py`

`hindi_title` didn't exist when the first ~3,255 rows were added, so
they're all `NULL` until backfilled. This script finds rows where
`hindi_title IS NULL`, translates them via Claude in batches of 15
(title + year only), and writes back with `movie_db.update_hindi_titles()`.

```bash
python3 tools/backfill_hindi_titles.py --limit 45
python3 tools/backfill_hindi_titles.py --dry-run
python3 tools/backfill_hindi_titles.py
```

- `--limit N` — cap how many rows get backfilled this run
- `--dry-run` — print proposed translations without writing

### 5. Backfill min_mime_seconds — `tools/backfill_min_mime_seconds.py`

`min_mime_seconds` didn't exist when most `hard`/`ultra_hard` rows were
curated (they predate this session's prompt update), so plenty are `NULL`.
This script finds rows where `difficulty IN ('hard', 'ultra_hard')` and
`min_mime_seconds IS NULL`, estimates a value from the title/year/mime_hint
via Claude in batches of 15, and writes back with
`movie_db.update_min_mime_seconds()`.

```bash
python3 tools/backfill_min_mime_seconds.py --limit 45
python3 tools/backfill_min_mime_seconds.py --dry-run
python3 tools/backfill_min_mime_seconds.py
```

- `--limit N` — cap how many rows get backfilled this run
- `--dry-run` — print proposed estimates without writing

## How `main.py` uses this database

This describes **offline mode** only (the default `movie_source` at
`/start`). On every `/reveal`, `main.py` calls `movie_db.all_movies()` and
picks one random entry not already in the session's `used_titles`
(`pick_offline_movie()`) — no filtering by `dumb_charades_ready` or
`difficulty`, and no upfront pool, so a session can run indefinitely
without running out of movies. Offline mode makes no LLM calls during
play. Claude is only used offline, by the `tools/` curation scripts, to
grow `data/movies.db` with new entries.

**Online mode** (`movie_source: "online"`, chosen at game start — see
[`GAME_ENGINE.md`](GAME_ENGINE.md)) bypasses this database entirely:
`generate_online_movie()` in `main.py` asks Claude for one movie live on
each `/reveal`, prompted with the same difficulty/mimeability criteria
above, and constrained to the `{title, year, difficulty, mime_hint,
min_mime_seconds}` shape via structured JSON output. It's only offered
when `ANTHROPIC_API_KEY` is configured.
