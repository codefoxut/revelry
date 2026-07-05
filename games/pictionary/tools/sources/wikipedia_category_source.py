"""Wikipedia category-tree source: BFS-crawls a category's subcategory tree
via the public MediaWiki API and collects article titles as candidate items.
No API key needed — just the read-only `action=query` endpoint.
"""

import sys
import time
from collections import deque

import requests

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "pictionary-data-tool/1.0 (offline category-list builder; no LLM calls)"
REQUEST_DELAY_SECONDS = 1.0
RETRY_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 5

_JUNK_MARKERS = (
    "disambiguation", "list of", "lists of", ":",
    "society", "journal", "expedition", "university", "institute",
    "conference", "symposium", "museum", "association", "committee",
)


def _is_junk(title: str) -> bool:
    lowered = title.lower()
    if any(marker in lowered for marker in _JUNK_MARKERS):
        return True
    first_word = title.split(" ", 1)[0]
    if len(first_word) == 4 and first_word.isdigit():
        return True
    return False


def _get_with_retry(params: dict) -> dict:
    last_error = None
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(API_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=20)
            if response.status_code == 429:
                wait = float(response.headers.get("Retry-After", RETRY_DELAY_SECONDS))
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS)
    raise last_error if last_error else RuntimeError("exhausted retries (repeated 429 Too Many Requests)")


def _category_members(category: str, cmtype: str, cmnamespace: str | None = None) -> list[str]:
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": category if category.startswith("Category:") else f"Category:{category}",
        "cmlimit": "500",
        "cmtype": cmtype,
        "format": "json",
    }
    if cmnamespace is not None:
        params["cmnamespace"] = cmnamespace

    while True:
        data = _get_with_retry(params)
        titles.extend(m["title"] for m in data.get("query", {}).get("categorymembers", []))
        time.sleep(REQUEST_DELAY_SECONDS)

        cont = data.get("continue")
        if not cont:
            break
        params.update(cont)

    return titles


def crawl_category(
    root_category: str,
    max_depth: int = 3,
    max_pages: int = 20000,
    max_categories: int = 400,
    max_seconds: float | None = None,
    verbose: bool = False,
) -> list[str]:
    """BFS the subcategory tree of `root_category` up to `max_depth`,
    collecting main-namespace article titles as candidates. Stops once
    `max_pages` results are collected, `max_categories` category nodes have
    been visited, or `max_seconds` wall-clock time has elapsed — whichever
    comes first. These bound runtime even against a bushy subcategory tree
    (or one where a single node needs many paginated `cmcontinue` requests)
    that would otherwise take a long time to exhaust at the API's ~1/sec
    rate-limited pace. Junk titles (disambiguation pages, "List of ..."
    pages, non-article namespaces) are filtered out.
    """
    start_time = time.monotonic()
    seen_lower = set()
    results = []
    seen_categories = {root_category}
    queue = deque([(root_category, 0)])
    categories_visited = 0

    while (
        queue
        and len(results) < max_pages
        and categories_visited < max_categories
        and (max_seconds is None or time.monotonic() - start_time < max_seconds)
    ):
        category, depth = queue.popleft()
        categories_visited += 1

        for title in _category_members(category, cmtype="page", cmnamespace="0"):
            if _is_junk(title):
                continue
            if title.lower() not in seen_lower:
                seen_lower.add(title.lower())
                results.append(title)
            if len(results) >= max_pages:
                break

        if verbose:
            print(
                f"    [{root_category}] visited {categories_visited}/{max_categories} categories "
                f"(queue={len(queue)}), {len(results)}/{max_pages} items — last: {category}",
                file=sys.stderr,
                flush=True,
            )

        if depth < max_depth:
            for subcat in _category_members(category, cmtype="subcat"):
                if subcat not in seen_categories:
                    seen_categories.add(subcat)
                    queue.append((subcat, depth + 1))

    return results
