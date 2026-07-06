"""IMDb non-commercial datasets source: public bulk TSV dumps (no key
required, https://developer.imdb.com/non-commercial-datasets/) filtered to
real Bollywood / pan-India movies.

title.basics has no region/language/origin field, and title.akas'
`isOriginalTitle` flag turns out to never carry a `region`/`language` value
in this dump (empirically: every isOriginalTitle == "1" row samples as a
null placeholder for both fields) — so there's no direct way to ask IMDb's
free dataset "is this film's origin country India?"

Instead, title.akas' region == "IN" + language in INDIAN_ORIGINAL_LANGUAGES
is used as a coarse *candidate* funnel (recall, not precision): it catches
every real Bollywood/pan-India film, but also plenty of foreign films
(Fight Club, Interstellar, ...) that merely have an India-market Hindi-dub
AKA on IMDb. Precision is handled downstream — tools/scrape_imdb_movies.py's
Claude curation step is told which titles came through this filter and asks
it to make the actual Indian-production call per title (`is_bollywood`),
dropping the false positives before insertion.

Sorting candidates by raw global vote count also skews hard toward that
same over-inclusion problem: the highest-voted titles in this candidate
pool are near-universally globally-famous non-Indian films (Shawshank
Redemption, The Dark Knight, ...), since those pick up Hindi dubs too and
simply have far more worldwide votes than most Indian films. Raising
`min_votes` doesn't fix this — it only trims the bottom of an
already-descending-sorted list, so the same mega-hits stay at the top
regardless of the floor. `max_votes` exists to cap the top of the range
instead, keeping the pool in a band where genuinely Indian titles are
actually competitive by vote count.

The same akas rows occasionally carry a genuine Hindi-language,
Devanagari-script alternate title (contributor-submitted, original or a
Hindi dub) — we opportunistically capture those as a real `hindi_title`,
since that beats an LLM guess when it exists.
"""

import csv
import gzip
import re
from pathlib import Path

import requests

csv.field_size_limit(10_000_000)

BASICS_URL = "https://datasets.imdbws.com/title.basics.tsv.gz"
RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
AKAS_URL = "https://datasets.imdbws.com/title.akas.tsv.gz"
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
BASICS_PATH = CACHE_DIR / "title.basics.tsv.gz"
RATINGS_PATH = CACHE_DIR / "title.ratings.tsv.gz"
AKAS_PATH = CACHE_DIR / "title.akas.tsv.gz"

INDIA_REGION = "IN"
# Major Indian film-industry languages (ISO 639-1/639-2 codes as used by
# IMDb) — used with INDIA_REGION as a coarse candidate filter; see the
# module docstring for why this over-includes and how that's handled.
INDIAN_ORIGINAL_LANGUAGES = {
    "hi", "te", "ta", "kn", "ml", "bn", "mr", "pa", "gu", "or", "as", "ur", "bho",
}
DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")


def _ensure_downloaded(url: str, path: Path) -> None:
    if path.exists():
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)


def _load_indian_akas() -> tuple[set[str], dict[str, str]]:
    """Returns (candidate tconsts released in India in an Indian language —
    over-inclusive, see module docstring — tconst -> Devanagari hindi_title)."""
    _ensure_downloaded(AKAS_URL, AKAS_PATH)
    candidate_tconsts = set()
    hindi_titles: dict[str, str] = {}
    with gzip.open(AKAS_PATH, mode="rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            tconst = row["titleId"]
            if row["region"] == INDIA_REGION and row["language"] in INDIAN_ORIGINAL_LANGUAGES:
                candidate_tconsts.add(tconst)
            if (
                tconst not in hindi_titles
                and row["language"] == "hi"
                and DEVANAGARI_RE.search(row["title"])
            ):
                hindi_titles[tconst] = row["title"].strip()
    return candidate_tconsts, hindi_titles


def _load_vote_counts() -> dict[str, int]:
    _ensure_downloaded(RATINGS_URL, RATINGS_PATH)
    votes = {}
    with gzip.open(RATINGS_PATH, mode="rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            votes[row["tconst"]] = int(row["numVotes"])
    return votes


def bollywood_titles(min_votes: int = 500, max_votes: int | None = 20000) -> list[dict]:
    """Candidate Bollywood/pan-India movie titles from IMDb's title.basics
    dump: titleType == "movie", released in India in an Indian language per
    title.akas (a coarse, over-inclusive filter — see module docstring),
    with `min_votes <= numVotes <= max_votes`. Sorted by vote count
    descending and deduped case-insensitively. Callers must still filter out
    non-Indian false positives (e.g. via Claude curation).

    `max_votes` defaults to 20000 to stay out of the global-blockbuster
    range where the candidate pool is dominated by non-Indian films (see
    module docstring); pass `None` to disable the ceiling.

    Each result: {"title": str, "year": int, "hindi_title": str | None}.
    """
    _ensure_downloaded(BASICS_URL, BASICS_PATH)
    candidate_tconsts, hindi_titles = _load_indian_akas()
    vote_counts = _load_vote_counts()

    candidates = []
    with gzip.open(BASICS_PATH, mode="rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row["titleType"] != "movie":
                continue
            tconst = row["tconst"]
            if tconst not in candidate_tconsts:
                continue
            votes = vote_counts.get(tconst)
            if votes is None or votes < min_votes:
                continue
            if max_votes is not None and votes > max_votes:
                continue
            title = row["primaryTitle"].strip()
            if not title:
                continue
            year_raw = row["startYear"]
            if year_raw == "\\N":
                continue
            candidates.append((votes, title, int(year_raw), hindi_titles.get(tconst)))

    candidates.sort(key=lambda item: item[0], reverse=True)

    seen_lower = set()
    results = []
    for _, title, year, hindi_title in candidates:
        if title.lower() not in seen_lower:
            seen_lower.add(title.lower())
            results.append({"title": title, "year": year, "hindi_title": hindi_title})
    return results
