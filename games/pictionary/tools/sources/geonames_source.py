"""GeoNames-backed source: the public "cities500" bulk dump (every populated
place with population >= 500) as candidate "places" items. No API key
needed — it's a plain static file download.
"""

import zipfile
from pathlib import Path

import requests

CITIES_URL = "https://download.geonames.org/export/dump/cities500.zip"
CACHE_DIR = Path(__file__).resolve().parent / ".cache"
ZIP_PATH = CACHE_DIR / "cities500.zip"
TXT_PATH = CACHE_DIR / "cities500.txt"

# geonames cities500.txt column layout (tab-separated, no header row):
# geonameid, name, asciiname, alternatenames, latitude, longitude,
# feature class, feature code, country code, cc2, admin1 code, admin2 code,
# admin3 code, admin4 code, population, elevation, dem, timezone, modification date
NAME_COLUMN = 1


def _ensure_downloaded() -> None:
    if TXT_PATH.exists():
        return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    response = requests.get(CITIES_URL, timeout=120)
    response.raise_for_status()
    ZIP_PATH.write_bytes(response.content)
    with zipfile.ZipFile(ZIP_PATH) as zf:
        zf.extract("cities500.txt", CACHE_DIR)


def place_names() -> list[str]:
    """Every unique place name from the GeoNames cities500 dump, in file
    order (roughly alphabetical-by-country, not population-sorted).
    """
    _ensure_downloaded()

    seen_lower = set()
    results = []
    with open(TXT_PATH, encoding="utf-8") as f:
        for line in f:
            columns = line.rstrip("\n").split("\t")
            if len(columns) <= NAME_COLUMN:
                continue
            name = columns[NAME_COLUMN].strip()
            if not name or name.lower() in seen_lower:
                continue
            seen_lower.add(name.lower())
            results.append(name)
    return results
