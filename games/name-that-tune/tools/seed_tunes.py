"""Seed the melody bank (data/tunes.db).

Every tune here is a public-domain melody (composition copyright expired —
classical themes, folk songs, and traditional carols), hand-transcribed by
us into a simple monophonic note sequence: [note_name, duration_seconds].
This is our own original transcription data, not an audio recording of any
performance, so there's no licensing question — nothing here is "content"
in the copyright sense, just facts about a melody's pitches and rhythm.

Playback happens client-side via the Web Audio API (see static/index.html);
no audio files are shipped at all.

Idempotent — uses INSERT OR IGNORE via tunes_db.add_tunes, safe to re-run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tunes_db as db

CATEGORIES = [
    ("classical", "Classical", "🎻", "#7B2FF7", 0),
    ("nursery-rhymes", "Nursery Rhymes", "🧸", "#FF3E7F", 1),
    ("holiday", "Holiday", "🎄", "#33D17A", 2),
    ("folk-anthems", "Folk & Anthems", "🎺", "#FF8A3D", 3),
]

# Durations, in seconds, at a comfortable playback tempo.
E, Q, DQ, H = 0.2, 0.4, 0.6, 0.8

CLASSICAL = [
    ("Beethoven's 5th Symphony", [
        ("G4", E), ("G4", E), ("G4", E), ("Eb4", H),
        ("F4", E), ("F4", E), ("F4", E), ("D4", H),
    ]),
    ("Für Elise", [
        ("E5", E), ("D#5", E), ("E5", E), ("D#5", E), ("E5", E),
        ("B4", E), ("D5", E), ("C5", E), ("A4", H),
    ]),
    ("Ode to Joy", [
        ("E4", Q), ("E4", Q), ("F4", Q), ("G4", Q),
        ("G4", Q), ("F4", Q), ("E4", Q), ("D4", Q),
        ("C4", Q), ("C4", Q), ("D4", Q), ("E4", Q),
        ("E4", DQ), ("D4", E), ("D4", H),
    ]),
    ("Canon in D", [
        ("D3", H), ("A3", H), ("B3", H), ("F#3", H),
        ("G3", H), ("D3", H), ("G3", H), ("A3", H),
    ]),
    ("Ride of the Valkyries", [
        ("F#4", Q), ("A4", Q), ("B4", Q), ("D5", H),
        ("F#5", Q), ("D5", Q), ("B4", Q), ("A4", H),
    ]),
]

NURSERY_RHYMES = [
    ("Twinkle Twinkle Little Star", [
        ("C4", Q), ("C4", Q), ("G4", Q), ("G4", Q),
        ("A4", Q), ("A4", Q), ("G4", H),
        ("F4", Q), ("F4", Q), ("E4", Q), ("E4", Q),
        ("D4", Q), ("D4", Q), ("C4", H),
    ]),
    ("Happy Birthday", [
        ("G4", E), ("G4", E), ("A4", Q), ("G4", Q), ("C5", Q), ("B4", H),
        ("G4", E), ("G4", E), ("A4", Q), ("G4", Q), ("D5", Q), ("C5", H),
    ]),
    ("Mary Had a Little Lamb", [
        ("E4", Q), ("D4", Q), ("C4", Q), ("D4", Q),
        ("E4", Q), ("E4", Q), ("E4", H),
        ("D4", Q), ("D4", Q), ("D4", H),
        ("E4", Q), ("G4", Q), ("G4", H),
    ]),
    ("Row, Row, Row Your Boat", [
        ("C4", Q), ("C4", Q), ("C4", Q), ("D4", Q), ("E4", H),
        ("E4", Q), ("D4", Q), ("E4", Q), ("F4", Q), ("G4", H),
    ]),
    ("Old MacDonald Had a Farm", [
        ("G4", Q), ("G4", Q), ("G4", Q), ("D4", Q),
        ("E4", Q), ("E4", Q), ("D4", H),
        ("B4", Q), ("B4", Q), ("A4", Q), ("A4", Q), ("G4", H),
    ]),
    ("London Bridge Is Falling Down", [
        ("G4", Q), ("A4", Q), ("G4", Q), ("F4", Q),
        ("E4", Q), ("F4", Q), ("G4", H),
        ("D4", Q), ("E4", Q), ("F4", Q), ("E4", Q), ("F4", Q), ("G4", H),
    ]),
    ("Frère Jacques", [
        ("C4", Q), ("D4", Q), ("E4", Q), ("C4", Q),
        ("C4", Q), ("D4", Q), ("E4", Q), ("C4", Q),
        ("E4", Q), ("F4", Q), ("G4", H),
        ("E4", Q), ("F4", Q), ("G4", H),
    ]),
]

HOLIDAY = [
    ("Jingle Bells", [
        ("E4", Q), ("E4", Q), ("E4", H),
        ("E4", Q), ("E4", Q), ("E4", H),
        ("E4", Q), ("G4", Q), ("C4", Q), ("D4", Q), ("E4", H),
    ]),
    ("Silent Night", [
        ("G4", Q), ("A4", Q), ("G4", Q), ("E4", H),
        ("G4", Q), ("A4", Q), ("G4", Q), ("E4", H),
    ]),
    ("We Wish You a Merry Christmas", [
        ("C4", Q), ("F4", Q), ("F4", Q), ("G4", Q), ("F4", Q), ("E4", Q), ("D4", Q),
        ("D4", Q), ("D4", Q), ("G4", Q), ("G4", Q), ("A4", Q), ("G4", Q), ("F4", Q),
        ("D4", Q), ("E4", Q), ("F4", H),
    ]),
    ("O Come All Ye Faithful", [
        ("G4", Q), ("G4", Q), ("A4", Q), ("G4", Q), ("E4", Q), ("F4", Q), ("G4", H),
        ("C5", Q), ("C5", Q), ("B4", Q), ("A4", Q), ("G4", H),
    ]),
]

FOLK_ANTHEMS = [
    ("Amazing Grace", [
        ("G4", Q), ("C5", H), ("E5", Q), ("C5", Q), ("E5", Q), ("D5", Q), ("C5", H),
    ]),
    ("Auld Lang Syne", [
        ("D4", Q), ("D4", Q), ("G4", Q), ("G4", Q),
        ("A4", Q), ("G4", Q), ("E4", Q), ("D4", H),
    ]),
    ("The Star-Spangled Banner", [
        ("D4", Q), ("G4", Q), ("B4", Q), ("D5", Q), ("E5", H), ("D5", Q), ("B4", H),
    ]),
]


def main() -> None:
    conn = db.get_connection()
    for category_id, name, emoji, color, sort_order in CATEGORIES:
        db.add_category(conn, category_id, name, emoji, color, sort_order)

    added = 0
    added += db.add_tunes(conn, "classical", CLASSICAL)
    added += db.add_tunes(conn, "nursery-rhymes", NURSERY_RHYMES)
    added += db.add_tunes(conn, "holiday", HOLIDAY)
    added += db.add_tunes(conn, "folk-anthems", FOLK_ANTHEMS)

    total = db.tune_count(conn, "mixed")
    print(f"Seeded {added} new tunes this run; {total} total in bank.")


if __name__ == "__main__":
    main()
