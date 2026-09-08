#!/usr/bin/env python3
"""Populate data/categories.db with a hand-curated offline word bank.

No scraping/LLM calls — this is the static fallback content used whenever
online (Claude) generation is unavailable or the player picks offline mode.
Safe to re-run: categories/items are inserted with OR IGNORE.

Usage:
    python3 tools/seed_categories.py
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import heads_up_db as db

CATEGORIES: list[tuple[str, str, str, str, list[str]]] = [
    (
        "animals", "Animals", "🐾", "#F2994A",
        [
            "Elephant", "Kangaroo", "Penguin", "Octopus", "Cheetah", "Giraffe",
            "Dolphin", "Gorilla", "Flamingo", "Koala", "Chameleon", "Peacock",
            "Sloth", "Hedgehog", "Platypus", "Ostrich", "Raccoon", "Otter",
            "Rhinoceros", "Hippopotamus", "Squirrel", "Owl", "Bat", "Shark",
            "Jellyfish", "Camel", "Panda", "Wolf", "Scorpion", "Parrot",
        ],
    ),
    (
        "movies", "Movies & TV", "🎬", "#EB5757",
        [
            "Titanic", "The Lion King", "Jurassic Park", "Frozen", "Inception",
            "The Matrix", "Finding Nemo", "Star Wars", "Harry Potter",
            "The Avengers", "Jaws", "Toy Story", "Home Alone", "Shrek",
            "The Godfather", "Spider-Man", "Batman", "Friends", "Breaking Bad",
            "Game of Thrones", "The Office", "Stranger Things", "SpongeBob SquarePants",
            "Rocky", "E.T.", "The Wizard of Oz", "Back to the Future",
            "Ratatouille", "Up", "The Simpsons",
        ],
    ),
    (
        "famous-people", "Famous People", "🌟", "#9B51E0",
        [
            "Albert Einstein", "Cleopatra", "William Shakespeare", "Beyoncé",
            "Mahatma Gandhi", "Michael Jackson", "Serena Williams", "Leonardo da Vinci",
            "Oprah Winfrey", "Elvis Presley", "Marie Curie", "Nelson Mandela",
            "Charlie Chaplin", "Frida Kahlo", "Muhammad Ali", "Walt Disney",
            "Steve Jobs", "Marilyn Monroe", "Abraham Lincoln", "Taylor Swift",
            "Pablo Picasso", "Amelia Earhart", "Bruce Lee", "Queen Elizabeth II",
            "Michael Jordan", "Vincent van Gogh", "Rosa Parks", "Elon Musk",
            "Lionel Messi", "David Beckham",
        ],
    ),
    (
        "occupations", "Occupations", "💼", "#2F80ED",
        [
            "Firefighter", "Astronaut", "Surgeon", "Chef", "Pilot", "Detective",
            "Photographer", "Librarian", "Electrician", "Plumber", "Lifeguard",
            "Veterinarian", "Architect", "Journalist", "Farmer", "Dentist",
            "Referee", "Tailor", "Barista", "Zookeeper", "Magician",
            "Lawyer", "Beekeeper", "Sculptor", "Translator", "Diplomat",
            "Locksmith", "Puppeteer", "Stunt Double", "Air Traffic Controller",
        ],
    ),
    (
        "actions", "Actions & Verbs", "🏃", "#27AE60",
        [
            "Juggling", "Sleepwalking", "Sneezing", "Yodeling", "Skydiving",
            "Milking a Cow", "Brushing Teeth", "Riding a Horse", "Surfing",
            "Playing the Drums", "Tightrope Walking", "Snowboarding", "Fishing",
            "Doing Yoga", "Bowling", "Rowing a Boat", "Skateboarding",
            "Flying a Kite", "Ice Skating", "Baking a Cake", "Hiccupping",
            "Wrestling", "Tap Dancing", "Blowing Bubbles", "Shoveling Snow",
            "Playing Chess", "Vacuuming", "Painting a Wall", "Texting",
            "Taking a Selfie",
        ],
    ),
    (
        "food-drink", "Food & Drink", "🍕", "#F2C94C",
        [
            "Pizza", "Sushi", "Tacos", "Spaghetti", "Ice Cream", "Pancakes",
            "Popcorn", "Burrito", "Croissant", "Ramen", "Watermelon",
            "Chocolate Cake", "Hot Dog", "Dumplings", "Mango Lassi", "Samosa",
            "Milkshake", "Waffles", "Sushi Roll", "Curry", "Lemonade",
            "Doughnut", "Pretzel", "Nachos", "Falafel", "Butter Chicken",
            "Bubble Tea", "Cheesecake", "Kebab", "Smoothie",
        ],
    ),
    (
        "sports", "Sports", "🏅", "#56CCF2",
        [
            "Cricket", "Basketball", "Swimming", "Boxing", "Archery", "Golf",
            "Table Tennis", "Badminton", "Volleyball", "Rock Climbing",
            "Gymnastics", "Rugby", "Fencing", "Sumo Wrestling", "Curling",
            "Water Polo", "Weightlifting", "Skiing", "Surfing", "Cycling",
            "Marathon Running", "Diving", "Horse Racing", "Hockey",
            "Snowboarding", "Darts", "Bowling", "Kabaddi", "Polo", "Judo",
        ],
    ),
    (
        "around-the-house", "Around the House", "🏠", "#BB6BD9",
        [
            "Toaster", "Umbrella", "Alarm Clock", "Vacuum Cleaner", "Doormat",
            "Ceiling Fan", "Refrigerator", "Flashlight", "Mirror", "Candle",
            "Broom", "Thermostat", "Bookshelf", "Doorbell", "Blender",
            "Watering Can", "Clothesline", "Rocking Chair", "Wind Chime",
            "Fire Extinguisher", "Welcome Mat", "Toolbox", "Lawnmower",
            "Curtains", "Light Switch", "Trash Can", "Ironing Board",
            "Ladder", "Garden Hose", "Wall Clock",
        ],
    ),
]


def main() -> None:
    conn = db.get_connection()
    total_categories = 0
    total_items = 0
    for sort_order, (cid, name, emoji, color, items) in enumerate(CATEGORIES):
        db.add_category(conn, cid, name, emoji, color, sort_order)
        total_categories += 1
        added = db.add_items(conn, cid, items)
        total_items += added
        print(f"  {emoji} {name}: {added} new items (pool now {db.item_count(conn, cid)})")
    conn.close()
    print(f"\n✅ Seeded {total_categories} categories, {total_items} new items.")


if __name__ == "__main__":
    main()
