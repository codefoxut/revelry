"""IMDb non-commercial datasets source: public bulk TSV dumps (no key
required, https://developer.imdb.com/non-commercial-datasets/) filtered to
real theatrical movies, ranked by vote count so the most recognizable
titles come first.
"""

import csv
import gzip
from pathlib import Path

import requests

BASICS_URL = "https://datasets.imdbws.com/title.basics.tsv.gz"
RATINGS_URL = "https://datasets.imdbws.com/title.ratings.tsv.gz"
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
BASICS_PATH = CACHE_DIR / "title.basics.tsv.gz"
RATINGS_PATH = CACHE_DIR / "title.ratings.tsv.gz"


def _ensure_downloaded(url: str, path: Path) -> None:
    if path.exists():
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)


def _load_vote_counts() -> dict[str, int]:
    _ensure_downloaded(RATINGS_URL, RATINGS_PATH)
    votes = {}
    with gzip.open(RATINGS_PATH, mode="rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            votes[row["tconst"]] = int(row["numVotes"])
    return votes


def movie_titles(min_votes: int = 1000) -> list[str]:
    """Real movie titles from IMDb's title.basics dump, restricted to
    titleType == "movie" and at least `min_votes` ratings (a proxy for
    "recognizable enough to guess from a sketch"), sorted by vote count
    descending and deduped case-insensitively.
    """
    _ensure_downloaded(BASICS_URL, BASICS_PATH)
    vote_counts = _load_vote_counts()

    candidates = []
    with gzip.open(BASICS_PATH, mode="rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row["titleType"] != "movie":
                continue
            votes = vote_counts.get(row["tconst"])
            if votes is None or votes < min_votes:
                continue
            title = row["primaryTitle"].strip()
            if title:
                candidates.append((votes, title))

    candidates.sort(key=lambda pair: pair[0], reverse=True)

    seen_lower = set()
    results = []
    for _, title in candidates:
        if title.lower() not in seen_lower:
            seen_lower.add(title.lower())
            results.append(title)
    return results
