"""Pure data pull from Wikidata's public SPARQL endpoint (Wikidata Query
Service) into data/personalities.db. No LLM calls — same spirit as the
sibling bollywood-dumbcharades app's tools/sources/imdb_source.py, which
pulls from IMDb's public dataset dumps rather than asking Claude to invent
titles.

Two categories, both drawing from the same `personalities` table (see
personality_db.py):

- `india`: humans whose country of citizenship (P27) is India (Q668).
  Wikidata has ~95k such items total (verified via a COUNT query) — that's
  the real ceiling for this category regardless of --target.
- `world`: humans matched by occupation with no citizenship filter (Indians
  included — the game's "World" pool is a superset of "Indian", not a
  disjoint set, per the product requirement). This is the pool that can
  comfortably exceed 100k since Wikidata has millions of humans overall.

Why occupation-scoped queries instead of one global query
-----------------------------------------------------------
A single query like "every human ordered by sitelinks descending" times out
against the public endpoint (60s query limit) once it has to sort millions
of rows with only a weak filter — confirmed empirically while building this
script. Scoping each query to one occupation (P106 = a specific QID, e.g.
"politician") makes the triple pattern selective enough to sort quickly.
OCCUPATIONS below is a broad-coverage list (politics/cinema/sport/science/
literature/business/etc.) iterated in turn; overlap between occupations is
expected and handled by dedup, not avoided.

Two-phase per occupation
-------------------------
1. `_candidate_qids()` — cheap keyset-paginated query for just
   (?person, ?sitelinks), ordered by sitelinks descending. Keyset pagination
   (carrying the last sitelinks/qid seen) is used instead of SPARQL OFFSET,
   which degrades badly at depth on a sorted set this large.
2. `_enrich_batch()` — a small VALUES-bound query (a few hundred QIDs) that
   pulls name/description/gender/dates/occupation/citizenship. Deliberately
   NOT using GROUP_CONCAT to aggregate multi-valued properties (occupation,
   citizenship) — empirically, Blazegraph's wikibase:label SERVICE does not
   reliably bind labels for variables that also feed a GROUP BY/aggregate in
   the same query (returns empty strings). Instead this fetches one row per
   (person, occupation, citizenship) combination and dedups/joins in Python.

Resumable: dedups against personality_db.existing_qids() before enriching,
and writes through personality_db.insert_personalities() (which itself
dedups by wikidata_qid), so an interrupted run can simply be re-started.
"""

import argparse
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import personality_db  # noqa: E402

SPARQL_URL = "https://query.wikidata.org/sparql"
USER_AGENT = "GuessThePersonalityBot/1.0 (party-game personality database; contact: local-dev)"
INDIA_QID = "Q668"

# Broad-coverage occupation taxonomy (Wikidata occupation QIDs). Overlap
# across categories is fine — dedup happens at insert time.
OCCUPATIONS: list[tuple[str, str]] = [
    ("Q82955", "politician"),
    ("Q33999", "actor"),
    ("Q177220", "singer"),
    ("Q639669", "musician"),
    ("Q36834", "composer"),
    ("Q2066131", "athlete"),
    ("Q937857", "association football player"),
    ("Q12299841", "cricketer"),
    ("Q3665646", "basketball player"),
    ("Q10833314", "tennis player"),
    ("Q11338576", "boxer"),
    ("Q10873124", "chess player"),
    ("Q36180", "writer"),
    ("Q49757", "poet"),
    ("Q1930187", "journalist"),
    ("Q901", "scientist"),
    ("Q169470", "physicist"),
    ("Q593644", "chemist"),
    ("Q864503", "biologist"),
    ("Q170790", "mathematician"),
    ("Q2526255", "film director"),
    ("Q3282637", "film producer"),
    ("Q1028181", "painter"),
    ("Q1281618", "sculptor"),
    ("Q131524", "entrepreneur"),
    ("Q43845", "businessperson"),
    ("Q40348", "lawyer"),
    ("Q189290", "military officer"),
    ("Q1058314", "religious leader"),
    ("Q188094", "economist"),
    ("Q201788", "historian"),
    ("Q4964182", "philosopher"),
    ("Q245068", "comedian"),
    ("Q4610556", "model"),
    ("Q5716684", "dancer"),
    ("Q42973", "architect"),
    ("Q81096", "engineer"),
    ("Q39631", "physician"),
    ("Q1622272", "university teacher"),
    ("Q15253558", "social activist"),
    ("Q3068305", "chef"),
    ("Q947873", "television presenter"),
]


def _get(query: str, timeout: int = 55, retries: int = 4) -> dict | None:
    """GET a SPARQL query with retries/backoff. Returns parsed JSON, or None
    if every attempt failed (caller should skip/continue, not crash the
    whole run over one flaky query)."""
    for attempt in range(retries):
        try:
            r = requests.get(
                SPARQL_URL,
                params={"query": query, "format": "json"},
                headers={"User-Agent": USER_AGENT},
                timeout=timeout,
            )
            if r.status_code == 200:
                return r.json()
            # 429/502/503/504 -> transient, worth retrying with backoff
        except requests.exceptions.RequestException:
            pass
        time.sleep(2 ** attempt)
    return None


def _qid_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


_QID_RE = re.compile(r"^Q\d+$")


def _has_real_label(name: str | None) -> bool:
    """The wikibase:label SERVICE falls back to the entity's own QID string
    (e.g. "Q1058") when no label exists in the requested language — that's
    not a name, so treat it as missing."""
    return bool(name) and not _QID_RE.match(name)


def _candidate_qids(occupation_qid: str, category: str, min_sitelinks: int, page_size: int):
    """Yield (qid, sitelinks) tuples for one occupation, paginated via
    keyset pagination on (sitelinks DESC, person ASC)."""
    citizenship_clause = f"?person wdt:P27 wd:{INDIA_QID} ." if category == "india" else ""
    last_sitelinks = None
    last_qid = None
    while True:
        cursor_clause = ""
        if last_sitelinks is not None:
            cursor_clause = f"""
            FILTER (?sitelinks < {last_sitelinks} ||
                    (?sitelinks = {last_sitelinks} && STR(?person) > STR(wd:{last_qid})))
            """
        query = f"""
        SELECT ?person ?sitelinks WHERE {{
          ?person wdt:P106 wd:{occupation_qid} .
          {citizenship_clause}
          ?person wikibase:sitelinks ?sitelinks .
          FILTER (?sitelinks >= {min_sitelinks})
          {cursor_clause}
        }}
        ORDER BY DESC(?sitelinks) ?person
        LIMIT {page_size}
        """
        data = _get(query)
        if data is None:
            return
        bindings = data["results"]["bindings"]
        if not bindings:
            return
        for b in bindings:
            qid = _qid_from_uri(b["person"]["value"])
            sitelinks = int(b["sitelinks"]["value"])
            yield qid, sitelinks
            last_sitelinks = sitelinks
            last_qid = qid
        if len(bindings) < page_size:
            return


def _enrich_batch(qids: list[str]) -> dict[str, dict]:
    """Fetch name/description/gender/dates/occupation/citizenship for a
    batch of QIDs. Returns {qid: facts_dict}."""
    values = " ".join(f"wd:{q}" for q in qids)
    query = f"""
    SELECT ?person ?personLabel ?desc ?genderLabel ?birthdate ?deathdate
           ?occupationLabel ?citizenship ?citizenshipLabel WHERE {{
      VALUES ?person {{ {values} }}
      OPTIONAL {{ ?person wdt:P21 ?gender . }}
      OPTIONAL {{ ?person wdt:P569 ?birthdate . }}
      OPTIONAL {{ ?person wdt:P570 ?deathdate . }}
      OPTIONAL {{ ?person wdt:P106 ?occupation . }}
      OPTIONAL {{ ?person wdt:P27 ?citizenship . }}
      OPTIONAL {{ ?person schema:description ?desc . FILTER(lang(?desc)="en") }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    data = _get(query, timeout=90)
    if data is None:
        return {}

    facts: dict[str, dict] = {}
    for b in data["results"]["bindings"]:
        qid = _qid_from_uri(b["person"]["value"])
        entry = facts.setdefault(
            qid,
            {
                "name": None,
                "description": None,
                "gender": None,
                "birth_year": None,
                "death_year": None,
                "occupations": set(),
                "citizenships": set(),
                "is_indian": False,
            },
        )
        if "personLabel" in b:
            entry["name"] = b["personLabel"]["value"]
        if "desc" in b:
            entry["description"] = b["desc"]["value"]
        if "genderLabel" in b:
            entry["gender"] = b["genderLabel"]["value"]
        if "birthdate" in b:
            entry["birth_year"] = int(b["birthdate"]["value"][:4])
        if "deathdate" in b:
            entry["death_year"] = int(b["deathdate"]["value"][:4])
        if "occupationLabel" in b:
            entry["occupations"].add(b["occupationLabel"]["value"])
        if "citizenship" in b:
            if _qid_from_uri(b["citizenship"]["value"]) == INDIA_QID:
                entry["is_indian"] = True
            if "citizenshipLabel" in b:
                entry["citizenships"].add(b["citizenshipLabel"]["value"])
    return facts


def run(category: str, target: int, min_sitelinks: int, page_size: int, batch_size: int,
        sleep: float, dry_run: bool) -> None:
    known_qids = personality_db.existing_qids()
    total_inserted = 0
    seen_this_run: set[str] = set()

    for occupation_qid, occupation_name in OCCUPATIONS:
        if total_inserted >= target:
            break
        print(f"== occupation: {occupation_name} ({occupation_qid}) ==")

        batch: list[str] = []
        for qid, sitelinks in _candidate_qids(occupation_qid, category, min_sitelinks, page_size):
            if qid in known_qids or qid in seen_this_run:
                continue
            seen_this_run.add(qid)
            batch.append(qid)

            if len(batch) >= batch_size:
                inserted = _process_batch(batch, category, dry_run)
                total_inserted += inserted
                print(f"  +{inserted} inserted (total {total_inserted}/{target})")
                batch = []
                time.sleep(sleep)
                if total_inserted >= target:
                    break

        if batch:
            inserted = _process_batch(batch, category, dry_run)
            total_inserted += inserted
            print(f"  +{inserted} inserted (total {total_inserted}/{target})")
            time.sleep(sleep)

    print(f"Done. Inserted {total_inserted} new '{category}' rows this run.")


def _process_batch(qids: list[str], category: str, dry_run: bool) -> int:
    facts = _enrich_batch(qids)
    rows = []
    for qid, f in facts.items():
        if not _has_real_label(f["name"]):
            continue
        is_indian = f["is_indian"] or category == "india"
        rows.append({
            "wikidata_qid": qid,
            "name": f["name"],
            "is_indian": is_indian,
            "nationality": ", ".join(sorted(f["citizenships"])) or None,
            "occupation": ", ".join(sorted(f["occupations"])) or None,
            "gender": f["gender"],
            "birth_year": f["birth_year"],
            "death_year": f["death_year"],
            "description": f["description"],
            "sitelinks": 0,
        })
    if dry_run:
        for r in rows[:5]:
            print("   ", r)
        return len(rows)
    return personality_db.insert_personalities(rows)


def main():
    parser = argparse.ArgumentParser(description="Scrape Wikidata into data/personalities.db")
    parser.add_argument("--category", choices=["india", "world"], required=True)
    parser.add_argument("--target", type=int, default=1000, help="stop once this many new rows are inserted")
    parser.add_argument("--min-sitelinks", type=int, default=3)
    parser.add_argument("--page-size", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=150, help="enrichment VALUES batch size")
    parser.add_argument("--sleep", type=float, default=1.0, help="seconds between enrichment requests")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(
        category=args.category,
        target=args.target,
        min_sitelinks=args.min_sitelinks,
        page_size=args.page_size,
        batch_size=args.batch_size,
        sleep=args.sleep,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
