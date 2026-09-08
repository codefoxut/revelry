"""Seed the offline emoji-puzzle bank (data/puzzles.db).

Idempotent — uses INSERT OR IGNORE via emoji_db.add_puzzles, safe to re-run.
Mirrors heads-up/tools/seed_categories.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import emoji_db as db

CATEGORIES = [
    ("movies", "Movies", "🎬", "#FF3E7F", 0),
    ("tv-shows", "TV Shows", "📺", "#7B2FF7", 1),
    ("phrases", "Phrases & Idioms", "💬", "#FF8A3D", 2),
]

MOVIES = [
    ("🦁👑", "The Lion King"),
    ("🕷️🧑", "Spider-Man"),
    ("❄️👸", "Frozen"),
    ("🦈", "Jaws"),
    ("🚢🧊💔", "Titanic"),
    ("🍫🏭", "Charlie and the Chocolate Factory"),
    ("🤖🚗", "Transformers"),
    ("🦇🦸‍♂️", "Batman"),
    ("👻🚫📞", "Ghostbusters"),
    ("🐠👨‍👦🔍", "Finding Nemo"),
    ("🦖🏝️", "Jurassic Park"),
    ("💍🌋🧙‍♂️", "The Lord of the Rings"),
    ("⚡👦🧙‍♂️", "Harry Potter"),
    ("🐝🎬", "Bee Movie"),
    ("🃏🤡", "Joker"),
    ("👠🕛👸", "Cinderella"),
    ("🧞‍♂️🪔", "Aladdin"),
    ("🦁🦓🦒🐒", "Madagascar"),
    ("🚗⚡🏎️", "Cars"),
    ("🐙🧜‍♀️", "The Little Mermaid"),
    ("👽📞🚲", "E.T. the Extra-Terrestrial"),
    ("🐍✈️", "Snakes on a Plane"),
    ("🎈🏠👴", "Up"),
    ("🐻🇵🇪🎩", "Paddington"),
    ("🚀👨‍🚀🌌", "Interstellar"),
]

TV_SHOWS = [
    ("🐉👑⚔️", "Game of Thrones"),
    ("🧪🥼🌵", "Breaking Bad"),
    ("👨‍👩‍👧‍👦😂🏠", "Modern Family"),
    ("📎🏢😐", "The Office"),
    ("🧛‍♂️🏠😂", "What We Do in the Shadows"),
    ("🕵️‍♂️🧠🔍", "Sherlock"),
    ("🙃👾🚲", "Stranger Things"),
    ("🏝️✈️💥", "Lost"),
    ("👑👵🇬🇧", "The Crown"),
    ("🧟‍♂️🏚️🔫", "The Walking Dead"),
    ("☕👫🗽", "Friends"),
    ("💰🎭🏦", "Money Heist"),
]

PHRASES = [
    ("🌧️🐱🐶", "Raining Cats and Dogs"),
    ("🍰🍽️", "Have Your Cake and Eat It Too"),
    ("🍎👨‍⚕️", "An Apple a Day Keeps the Doctor Away"),
    ("🐘🏠", "Elephant in the Room"),
    ("🍞🧈", "Bread and Butter"),
    ("🥧😐", "Easy as Pie"),
    ("💥🦵", "Break a Leg"),
    ("🍰", "Piece of Cake"),
    ("☁️🤒", "Under the Weather"),
    ("🌕🔵", "Once in a Blue Moon"),
    ("💵💪🦵", "Cost an Arm and a Leg"),
    ("🐱👜", "Let the Cat Out of the Bag"),
    ("🔨🔩🎯", "Hit the Nail on the Head"),
    ("⚽👉", "The Ball Is in Your Court"),
    ("🥁🌳", "Beat Around the Bush"),
    ("🗣️📢🔇", "Actions Speak Louder Than Words"),
    ("🦷🔫", "Bite the Bullet"),
    ("🐦🐦🪨", "Kill Two Birds With One Stone"),
    ("🔍💀🐱", "Curiosity Killed the Cat"),
    ("🐷✈️", "When Pigs Fly"),
    ("🍎🌳", "The Apple Doesn't Fall Far From the Tree"),
    ("☁️🥈", "Every Cloud Has a Silver Lining"),
    ("📖🚫👀", "Don't Judge a Book by Its Cover"),
    ("🗣️😈", "Speak of the Devil"),
    ("⛽🔥", "Add Fuel to the Fire"),
    ("🐕🌳❌", "Barking Up the Wrong Tree"),
    ("🙏🎭", "A Blessing in Disguise"),
    ("🔥🌙🛢️", "Burning the Midnight Oil"),
    ("🪨🧱", "Caught Between a Rock and a Hard Place"),
]


def main() -> None:
    conn = db.get_connection()
    for category_id, name, emoji, color, sort_order in CATEGORIES:
        db.add_category(conn, category_id, name, emoji, color, sort_order)

    added = 0
    added += db.add_puzzles(conn, "movies", MOVIES)
    added += db.add_puzzles(conn, "tv-shows", TV_SHOWS)
    added += db.add_puzzles(conn, "phrases", PHRASES)

    total = db.puzzle_count(conn, "mixed")
    print(f"Seeded {added} new puzzles this run; {total} total in bank.")


if __name__ == "__main__":
    main()
