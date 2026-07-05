#!/usr/bin/env python3
"""Grow data/categories.db — the static Pictionary item database — using
Claude to propose new, on-theme items (or an entirely new category).

data/categories.db backs two things in server.py: the category picker
(id/name/emoji/color) and the offline fallback list used when a live
Claude card-generation call fails mid-game. This script is how that
database gets bigger over time, instead of hand-editing rows.

Usage:
    python3 tools/update_categories.py                       # top up every category
    python3 tools/update_categories.py --category animals     # just one category
    python3 tools/update_categories.py --count 20 --dry-run
    python3 tools/update_categories.py --new-category --id monsters --name "Monsters" \\
        --emoji "\U0001F47E" --color "#dc2626" --count 15

Requires ANTHROPIC_API_KEY in the environment (source .env first, or run via
`make update-categories`).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import pictionary_db

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# ---------------------------------------------------------------------------
# Pictionary Item Curation Prompt — same golden rules server.py uses for
# live card generation, applied here to grow the permanent static list.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are curating the static item bank for a Pictionary \
party game.

Golden rules for Pictionary items:
1. DRAWABLE — must be sketchable in under 60 seconds.
2. GUESSABLE — teammates can recognise it from a quick sketch alone.
3. CONCRETE — prefer specific nouns or vivid action scenes over vague \
abstractions.
4. VARIED DIFFICULTY — mix easy, medium, and hard items.
5. FUN & SURPRISING — avoid the most obvious, overused choices when you can.

You will be given a category and a sample of items already in the bank for \
it. Propose new items that fit the category and are not duplicates or \
close rephrasings of anything in the sample.

Output ONLY a JSON array of strings, nothing else — no markdown fences, \
no prose, no commentary."""

USER_PROMPT_TEMPLATE = """\
Category: {name}
Sample of existing items ({sample_count} of {existing_count} total): {existing}

Generate exactly {n} NEW Pictionary items for this category. Do not repeat \
or closely rephrase any existing item.
Return ONLY a JSON array, e.g.: ["item one", "item two"]"""

NEW_CATEGORY_PROMPT_TEMPLATE = """\
Category: {name} (brand new category, no existing items yet)

Generate exactly {n} Pictionary items for this category.
Return ONLY a JSON array, e.g.: ["item one", "item two"]"""

EXISTING_SAMPLE_LIMIT = 50


def curate_items(prompt: str, n: int) -> list[str]:
    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    items = json.loads(raw)
    if not (isinstance(items, list) and all(isinstance(x, str) for x in items)):
        raise ValueError(f"Claude returned malformed items: {raw!r}")
    return items[:n]


def top_up_category(conn, category: dict, n: int) -> int:
    existing_count = pictionary_db.item_count(conn, category["id"])
    sample = pictionary_db.sample_items_for_prompt(conn, category["id"], EXISTING_SAMPLE_LIMIT)
    prompt = USER_PROMPT_TEMPLATE.format(
        name=category["name"],
        sample_count=len(sample),
        existing_count=existing_count,
        existing=", ".join(sample),
        n=n,
    )
    proposed = curate_items(prompt, n)
    return pictionary_db.add_items(conn, category["id"], proposed)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--category", help="only top up this category id (default: all categories)")
    parser.add_argument("--count", type=int, default=15, help="new items to request per category (default 15)")
    parser.add_argument("--dry-run", action="store_true", help="print proposed additions without writing")

    parser.add_argument("--new-category", action="store_true", help="create a brand new category instead of topping up")
    parser.add_argument("--id", help="new category id (slug), required with --new-category")
    parser.add_argument("--name", help="new category display name, required with --new-category")
    parser.add_argument("--emoji", help="new category emoji, required with --new-category")
    parser.add_argument("--color", help="new category hex color, required with --new-category")
    args = parser.parse_args()

    conn = pictionary_db.get_connection()

    if args.new_category:
        missing = [f"--{f}" for f in ("id", "name", "emoji", "color") if not getattr(args, f)]
        if missing:
            parser.error(f"--new-category requires {', '.join(missing)}")
        if pictionary_db.get_category(conn, args.id):
            parser.error(f"category id '{args.id}' already exists")

        prompt = NEW_CATEGORY_PROMPT_TEMPLATE.format(name=args.name, n=args.count)
        items = curate_items(prompt, args.count)

        print(f"New category '{args.name}' ({args.id}): {len(items)} items")
        if args.dry_run:
            print(json.dumps(items, indent=2, ensure_ascii=False))
            print("\n[dry-run] Would add this category. No rows written.")
            return

        existing_categories = pictionary_db.list_categories(conn)
        pictionary_db.add_category(conn, args.id, args.name, args.emoji, args.color, len(existing_categories))
        pictionary_db.add_items(conn, args.id, items)
        print(f"Added category '{args.name}' to {pictionary_db.DB_PATH}")
        return

    targets = pictionary_db.list_categories(conn)
    if args.category:
        targets = [c for c in targets if c["id"] == args.category]
        if not targets:
            parser.error(f"category id '{args.category}' not found")

    total_added = 0
    for category in targets:
        before = pictionary_db.item_count(conn, category["id"])
        if args.dry_run:
            sample = pictionary_db.sample_items_for_prompt(conn, category["id"], EXISTING_SAMPLE_LIMIT)
            prompt = USER_PROMPT_TEMPLATE.format(
                name=category["name"], sample_count=len(sample), existing_count=before,
                existing=", ".join(sample), n=args.count,
            )
            proposed = curate_items(prompt, args.count)
            print(f"{category['id']}: +{len(proposed)} proposed ({before} -> {before + len(proposed)})")
            total_added += len(proposed)
            continue

        added = top_up_category(conn, category, args.count)
        after = pictionary_db.item_count(conn, category["id"])
        print(f"{category['id']}: +{added} new items ({before} -> {after})")
        total_added += added

    if args.dry_run:
        print(f"\n[dry-run] Would add {total_added} items total. No rows written.")
        return

    print(f"\nAdded {total_added} items total to {pictionary_db.DB_PATH}")


if __name__ == "__main__":
    main()
