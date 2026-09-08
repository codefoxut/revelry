# Personality database

This app draws its "Guess the Personality" pool from `data/personalities.db`
(SQLite) instead of letting the LLM invent famous people from memory each
game. This file exists so any LLM (or human) picking up this project later
can extend the data correctly without needing prior conversation context.

## Why a database at all

Letting the host LLM freely pick a personality from memory each round is
unpredictable: names repeat across sessions, there's no control over which
facts are true, and it depends on the model not hallucinating a birth year
or occupation. A curated, queryable list fixes that — `main.py` samples
from it once per game and the LLM only writes clues/hosts from the sampled
facts, the same pattern `bollywood-dumbcharades` uses for movies (see its
`docs/MOVIE_DATABASE.md`).

SQLite (not a JSON file) is the storage format for the same reason as the
movie DB: it stays compact and indexed at 100k+ rows, where a pretty-printed
JSON file would become unwieldy to load and query.

## Schema

`data/personalities.db`, single table `personalities`:

| Column | Type | Notes |
|---|---|---|
| `id` | TEXT PK | `q<QID-number>`, e.g. `q9682` for Wikidata `Q9682` — stable across re-scrapes, used for dedup |
| `wikidata_qid` | TEXT UNIQUE | e.g. `Q9682` |
| `name` | TEXT | English label |
| `is_indian` | INTEGER | `1` if country of citizenship (Wikidata P27) includes India (`Q668`), else `0` |
| `nationality` | TEXT \| NULL | citizenship label(s), comma-separated (a person can have more than one, e.g. historical entities like "British Raj, India") |
| `occupation` | TEXT \| NULL | occupation label(s) (P106), comma-separated |
| `gender` | TEXT \| NULL | P21 label |
| `birth_year` | INTEGER \| NULL | from P569 |
| `death_year` | INTEGER \| NULL | from P570 — `NULL` means living or unknown |
| `description` | TEXT \| NULL | Wikidata's English short description, e.g. "Indian actor and film director" |
| `sitelinks` | INTEGER | wikibase sitelink count — a notability proxy; higher means more Wikipedia-language editions have an article, i.e. more likely to be recognizable in a party game |

Indexed on `is_indian` and `sitelinks` (mirrors `bollywood-dumbcharades`'s
`idx_movies_ready`/`idx_movies_year`).

There is deliberately **no pre-written clue text** per person (unlike the
movie DB's `mime_hint`) — `occupation` + `nationality` + `birth_year`/
`death_year` + `description` is enough raw material for Claude to write
cryptic→obvious clues live each round, and pre-authoring clue sets for
100k+ rows isn't practical the way it is for a few thousand movies.

"World" is not a separate pool from "India" — it's the **entire table**,
Indian personalities included. `category = "india"` is just
`WHERE is_indian = 1` on the same table. This was a deliberate product
choice: an Indian celebrity should be a legitimately possible answer in a
"World" game, not excluded from it.

All access goes through `personality_db.py` (project root) — `main.py` and
`tools/scrape_wikidata_personalities.py` import it rather than touching
SQLite directly. Key functions: `count(category)`,
`sample_personalities(category, n, pool_multiplier=20)`, `existing_qids()`,
`slug_id(qid)`, `insert_personalities(list[dict]) -> int`.

## Data source: Wikidata

[Wikidata Query Service](https://query.wikidata.org/sparql) — free, no
auth, SPARQL over HTTP. Chosen because it's the only source with
structured, queryable data (occupation, citizenship, birth/death dates,
notability) across both Indian and international public figures at 100k+
scale, without per-row LLM cost (same "pure data pull" spirit as
`bollywood-dumbcharades/tools/sources/imdb_source.py`, which pulls IMDb's
public dataset dumps instead of asking Claude to invent movie titles).

### Why occupation-scoped queries

A single query like "every human (`wdt:P31 wd:Q5`), ordered by sitelinks
descending" reliably times out or 502s against the public endpoint — it has
to sort tens of millions of rows behind a very weak filter, and WDQS
enforces a ~60 second query budget. Scoping each query to one occupation
(`wdt:P106` = a specific QID, e.g. "politician") makes the triple pattern
selective enough that the endpoint returns in a few seconds. The scraper
iterates a curated list of ~40 occupation QIDs (`OCCUPATIONS` in the
script) spanning politics, cinema, sport, science, literature, business,
etc. Overlap between occupations is expected (someone can be both an
"actor" and a "politician") and is handled by dedup, not avoided.

### Two-phase scrape per occupation

1. **Candidate discovery** (`_candidate_qids`) — a cheap query for just
   `(?person, ?sitelinks)`, filtered by occupation (and, for the `india`
   category, also by `wdt:P27 wd:Q668`), ordered by
   `sitelinks DESC, person ASC`. Paginated by **keyset pagination**, not
   `OFFSET`: each page carries the last `(sitelinks, qid)` seen and asks for
   rows strictly after that in sort order
   (`?sitelinks < :last OR (?sitelinks = :last AND ?person > :lastQid)`).
   `OFFSET` degrades badly at depth on a sorted set this large; keyset
   pagination stays fast at any depth.
2. **Enrichment** (`_enrich_batch`) — batches of ~150 QIDs at a time via a
   `VALUES ?person { wd:Q... wd:Q... }` query, pulling name, description,
   gender, birth/death dates, and **every** occupation/citizenship value
   (not just the one used to find them). Deliberately **not** using
   `GROUP_CONCAT` to aggregate the multi-valued occupation/citizenship
   fields in SPARQL — empirically, Blazegraph's `SERVICE wikibase:label`
   does not reliably bind labels for a variable that's also being
   aggregated in the same query (it silently returns an empty string
   instead of erroring). The workaround: fetch one row per
   (person, occupation, citizenship) combination — an intentional
   cartesian join — and group/dedupe/join the labels in Python instead.

One more label-service quirk this script guards against: when an entity
has no English label at all, `SERVICE wikibase:label` falls back to
returning the entity's own QID string (e.g. `"Q1058"`) as the "label"
instead of erroring or omitting it. `_has_real_label()` filters these out
before insert — otherwise they'd show up in-game as a "personality" named
literally `Q1058`.

## Extending the database

### `tools/scrape_wikidata_personalities.py`

```bash
python3 tools/scrape_wikidata_personalities.py --category india --target 100000
python3 tools/scrape_wikidata_personalities.py --category world --target 100000
python3 tools/scrape_wikidata_personalities.py --category india --target 200 --dry-run
```

- `--category india|world` — required. `india` filters to India citizenship
  server-side; `world` has no citizenship filter (Indians naturally appear
  in it too, per the "World is a superset" design above).
- `--target N` — stop once this many *new* rows have been inserted this run
  (default 1000). Already-known QIDs (already in the DB, or already seen
  earlier in the same run) don't count against the target and aren't
  re-enriched.
- `--min-sitelinks N` — quality floor on the candidate query (default 3) —
  raise it to bias toward more recognizable people, lower it to reach a
  larger `--target` at the cost of some very obscure entries.
- `--page-size N` — candidate query page size (default 2000).
- `--batch-size N` — enrichment `VALUES` batch size (default 150).
- `--sleep N` — seconds to wait between enrichment requests (default 1.0)
  — stay polite to the shared public endpoint.
- `--dry-run` — print what would be inserted without writing to the DB.

**Resumable by design**: every batch is written to the database as soon as
it's enriched (not held in memory until the whole run finishes), and
`existing_qids()` is checked before both discovery and enrichment — killing
the process (or it crashing on a flaky request) loses at most one in-flight
batch. Re-running the same command continues from wherever it left off.

**Known ceiling for `india`**: Wikidata has roughly 94-95k humans with
India listed as country of citizenship in total (verified via a `COUNT`
query during development) — `--target 100000` on this category will
plateau there rather than reach exactly 100k. This is a real data
availability limit, not a bug in the scraper. `world` has no such ceiling
since it isn't citizenship-filtered.

## How `main.py` uses this database

At `POST /start`, `personality_db.sample_personalities(category, 50)` draws
50 people for the chosen category, biased toward higher `sitelinks` (it
samples uniformly from the top `50 * 20` rows by sitelinks rather than the
full table, so a game stays reasonably recognizable rather than drawing
from the very obscure tail). That list is stored once in the session file
as `personality_pool` and reused verbatim for the rest of that game — see
[`DESIGN.md`](DESIGN.md) for how it's injected into the system prompt via
`{PERSONALITY_POOL}` and why it's sampled once per game, not once per
round.
