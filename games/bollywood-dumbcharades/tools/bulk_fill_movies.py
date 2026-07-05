#!/usr/bin/env python3
"""Bulk-fill the movie database across a range of years by looping
tools/scrape_wiki_movies.py's fetch -> curate -> insert pipeline year by year.

Usage:
    python3 tools/bulk_fill_movies.py --start 1927 --end 2026
    python3 tools/bulk_fill_movies.py --start 1927 --end 1950 --dry-run
    python3 tools/bulk_fill_movies.py --start 1927 --end 2026 --skip-existing 15

Requires ANTHROPIC_API_KEY in the environment or a .env file (same as the
other tools/ scripts). Wikipedia connections are occasionally flaky in this
environment, so each year is retried a few times before being skipped.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import movie_db
from scrape_wiki_movies import curate_titles, extract_titles, fetch_page

RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5
REQUEST_DELAY_SECONDS = 2


def fill_year(year: int, dry_run: bool) -> tuple[int, int]:
    html = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            html = fetch_page(year)
            break
        except Exception as exc:
            if attempt == RETRY_ATTEMPTS:
                print(f"  [{year}] FAILED after {RETRY_ATTEMPTS} attempts: {exc}")
                return 0, 0
            print(f"  [{year}] fetch attempt {attempt} failed ({exc}), retrying in {RETRY_DELAY_SECONDS}s...")
            time.sleep(RETRY_DELAY_SECONDS)

    scraped = extract_titles(html)
    known = movie_db.existing_titles_lower()
    fresh = [t for t in scraped if t.lower() not in known]

    if not fresh:
        print(f"  [{year}] scraped {len(scraped)} titles, nothing new to curate")
        return 0, 0

    all_normalized = curate_titles(fresh, year)

    ready_count = sum(1 for m in all_normalized if m["dumb_charades_ready"])

    if dry_run:
        print(f"  [{year}] would add {len(all_normalized)} movies ({ready_count} ready)")
        return len(all_normalized), ready_count

    added = movie_db.insert_movies(all_normalized)
    print(f"  [{year}] added {added} movies ({ready_count} ready)")
    return added, ready_count


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", type=int, required=True, help="first year, e.g. 1927")
    parser.add_argument("--end", type=int, required=True, help="last year, inclusive, e.g. 2026")
    parser.add_argument(
        "--step", type=int, default=1,
        help="year stride, e.g. 3 to sample every 3rd year (default 1 = every year)",
    )
    parser.add_argument(
        "--skip-existing", type=int, default=None,
        help="skip a year if the DB already has at least this many movies for it",
    )
    parser.add_argument("--dry-run", action="store_true", help="print proposed additions without writing")
    args = parser.parse_args()

    years = list(range(args.start, args.end + 1, args.step))
    print(f"Filling {len(years)} year(s) from {args.start} to {args.end} (step {args.step}, no per-year limit)")

    existing_year_counts: dict[int, int] = {}
    if args.skip_existing is not None:
        for m in movie_db.all_movies():
            existing_year_counts[m["year"]] = existing_year_counts.get(m["year"], 0) + 1

    total_added = 0
    total_ready = 0
    skipped_years = []

    for i, year in enumerate(years, 1):
        if args.skip_existing is not None and existing_year_counts.get(year, 0) >= args.skip_existing:
            skipped_years.append(year)
            continue
        print(f"[{i}/{len(years)}] year {year}")
        added, ready = fill_year(year, args.dry_run)
        total_added += added
        total_ready += ready
        if i < len(years):
            time.sleep(REQUEST_DELAY_SECONDS)

    if skipped_years:
        print(f"\nSkipped {len(skipped_years)} year(s) already at/above --skip-existing threshold: {skipped_years}")
    verb = "Would add" if args.dry_run else "Added"
    print(f"\n{verb} {total_added} movies total ({total_ready} dumb-charades-ready) across {len(years) - len(skipped_years)} year(s)")


if __name__ == "__main__":
    main()
