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
| `year`                 | INTEGER | theatrical release year                                                 |
| `decade`               | TEXT    | derived from `year`, formatted `"1990s"`, `"2000s"`, etc.               |
| `genres`               | TEXT    | comma-separated lowercase, e.g. `"action,drama"`                        |
| `language`             | TEXT    | `"Hindi"` for Hindi-original films; original language (e.g. `"Telugu"`) for pan-India hits watched in Hindi dub |
| `difficulty`           | TEXT    | `"easy" \| "medium" \| "hard"` — how hard to guess once mimed           |
| `dumb_charades_ready`  | INTEGER | `0`/`1` — `1` only if the title is genuinely mimeable — see criteria below |
| `mime_hint`            | TEXT \| NULL | one short phrase suggesting how to act it out; set when `dumb_charades_ready = 1`, otherwise `NULL` |
| `tags`                 | TEXT    | comma-separated: franchise, actor, cult status, era                     |
| `franchise`            | TEXT \| NULL | franchise/series name if part of one, else `NULL`                 |

Indexed on `dumb_charades_ready` and `year` for cheap filtering.

All access goes through `movie_db.py` (project root) — `main.py` and both
`tools/` scripts import it rather than touching SQLite directly. Key
functions: `all_movies()`, `ready_movies()`, `existing_ids()`,
`existing_titles_lower()`, `slugify(title)`, `normalize(entry,
force_year=None)`, `insert_movies(list[dict]) -> int`.

## `dumb_charades_ready` criteria

A title is `true`/`1` only if it satisfies all of:
1. **Short or iconic** — mimeable in well under a minute.
2. **Concrete** — has a recognizable object, action, character, or scene
   (a sword, a wrestling move, a moon, a train) rather than being pure
   abstract wordplay.
3. **Recognizable** — a mimed gesture would plausibly let a teammate guess
   the title, not just its general vibe.

Abstract phrases, idioms, or pure feelings with no concrete gesture (e.g.
*Kuch Kuch Hota Hai*) should be `false`.

## Extending the database

Two ways to grow it — both write through `movie_db.py`, so `id` slugs,
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

## How `main.py` uses this database

This describes **offline mode** only (the default `movie_source` at
`/start`). `main.py` calls `movie_db.ready_movies()` and samples a shuffled
pool of `dumb_charades_ready` entries once per game session
(`sample_movie_pool()`), storing it in the session's game state. Offline
mode is fully deterministic — `main.py` pops movies off the pool and drives
scoring directly with no LLM calls during play. Claude is only used
offline, by the `tools/` curation scripts, to grow `data/movies.db` with
new entries.

**Online mode** (`movie_source: "online"`, chosen at game start — see
[`GAME_ENGINE.md`](GAME_ENGINE.md)) bypasses this database entirely:
`generate_online_movie()` in `main.py` asks Claude for one movie live on
each `/reveal`, prompted with the same mimeability criteria as
`dumb_charades_ready` above, and constrained to the `{title, year,
difficulty, mime_hint}` shape via structured JSON output. It's only offered
when `ANTHROPIC_API_KEY` is configured.
