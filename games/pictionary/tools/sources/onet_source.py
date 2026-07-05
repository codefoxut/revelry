"""O*NET-backed source: the public "Alternate Titles" database text dump
(https://www.onetcenter.org/database.html — public domain, US Dept of
Labor, no API key) as candidate "professions" items.
"""

import csv
from pathlib import Path

import requests

ALTERNATE_TITLES_URL = (
    "https://www.onetcenter.org/dl_files/database/db_29_1_text/Alternate%20Titles.txt"
)
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
ALTERNATE_TITLES_PATH = CACHE_DIR / "onet_alternate_titles.txt"


def _ensure_downloaded() -> None:
    if ALTERNATE_TITLES_PATH.exists():
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    response = requests.get(ALTERNATE_TITLES_URL, timeout=60)
    response.raise_for_status()
    ALTERNATE_TITLES_PATH.write_bytes(response.content)


def profession_titles() -> list[str]:
    """Unique occupation title strings from O*NET's Alternate Titles and
    Short Titles columns (the canonical "Title" column lives in a separate
    file keyed by SOC code, which isn't needed here — alternate/short
    titles alone comfortably cover the target volume).
    """
    _ensure_downloaded()

    seen_lower = set()
    results = []
    with open(ALTERNATE_TITLES_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            for column in ("Alternate Title", "Short Title"):
                title = row.get(column, "").strip()
                if not title or title.lower() == "n/a":
                    continue
                if title.lower() not in seen_lower:
                    seen_lower.add(title.lower())
                    results.append(title)
    return results
