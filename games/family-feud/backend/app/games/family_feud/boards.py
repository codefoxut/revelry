from dataclasses import dataclass


@dataclass(frozen=True)
class Answer:
    text: str
    points: int


@dataclass(frozen=True)
class Board:
    prompt: str
    answers: list[Answer]  # sorted descending by points; should sum to 100


BOARD_BANK: list[Board] = [
    Board(
        "Name something people do first thing in the morning",
        [
            Answer("Check their phone", 35),
            Answer("Brush their teeth", 25),
            Answer("Make coffee", 18),
            Answer("Take a shower", 12),
            Answer("Check the time", 7),
            Answer("Stretch or exercise", 3),
        ],
    ),
    Board(
        "Name something you would find in a refrigerator",
        [
            Answer("Milk", 30),
            Answer("Leftovers", 22),
            Answer("Vegetables", 18),
            Answer("Juice", 14),
            Answer("Condiments / ketchup", 10),
            Answer("Eggs", 6),
        ],
    ),
    Board(
        "Name a reason someone might call in sick to work",
        [
            Answer("Headache / migraine", 28),
            Answer("Fever or cold", 25),
            Answer("Family emergency", 20),
            Answer("Stomach ache", 15),
            Answer("Just tired", 8),
            Answer("Doctor appointment", 4),
        ],
    ),
    Board(
        "Name something you would take to the beach",
        [
            Answer("Sunscreen", 32),
            Answer("Towel", 26),
            Answer("Water or drinks", 19),
            Answer("Sunglasses", 13),
            Answer("Snacks or food", 7),
            Answer("Hat", 3),
        ],
    ),
    Board(
        "Name something you would find in a fast food meal",
        [
            Answer("Burger or sandwich", 38),
            Answer("Fries", 28),
            Answer("Drink or soda", 18),
            Answer("Sauce or ketchup", 10),
            Answer("Napkins", 6),
        ],
    ),
    Board(
        "Name something people do on a first date",
        [
            Answer("Dinner at a restaurant", 32),
            Answer("See a movie", 25),
            Answer("Go for a walk", 18),
            Answer("Go bowling", 13),
            Answer("Get coffee", 8),
            Answer("Mini-golf", 4),
        ],
    ),
    Board(
        "Name something you would find in a gym",
        [
            Answer("Weights or dumbbells", 34),
            Answer("Treadmill", 28),
            Answer("Mirrors", 16),
            Answer("Yoga mat", 12),
            Answer("Locker room", 6),
            Answer("Water fountain", 4),
        ],
    ),
    Board(
        "Name something people are commonly afraid of",
        [
            Answer("Spiders", 30),
            Answer("Snakes", 25),
            Answer("Heights", 20),
            Answer("The dark", 14),
            Answer("Public speaking", 7),
            Answer("Dogs", 4),
        ],
    ),
    Board(
        "Name something associated with New Year's Eve",
        [
            Answer("Fireworks", 35),
            Answer("Champagne or drinks", 28),
            Answer("Countdown", 18),
            Answer("Party or celebration", 12),
            Answer("Resolutions", 7),
        ],
    ),
    Board(
        "Name something you would bring to a potluck dinner",
        [
            Answer("Salad", 28),
            Answer("Pasta dish", 22),
            Answer("Dessert or cake", 20),
            Answer("Chips and dip", 16),
            Answer("Casserole", 9),
            Answer("Drinks", 5),
        ],
    ),
    Board(
        "Name something people do at a birthday party",
        [
            Answer("Eat cake", 35),
            Answer("Sing happy birthday", 28),
            Answer("Open gifts", 20),
            Answer("Play games", 10),
            Answer("Take photos", 7),
        ],
    ),
    Board(
        "Name a common household pet",
        [
            Answer("Dog", 42),
            Answer("Cat", 30),
            Answer("Fish", 14),
            Answer("Bird or parrot", 9),
            Answer("Rabbit", 5),
        ],
    ),
    Board(
        "Name something you would pack for a camping trip",
        [
            Answer("Tent", 35),
            Answer("Sleeping bag", 28),
            Answer("Food or snacks", 18),
            Answer("Flashlight", 12),
            Answer("Bug spray", 7),
        ],
    ),
    Board(
        "Name something that makes a house smell good",
        [
            Answer("Candles", 32),
            Answer("Fresh bread or cooking", 25),
            Answer("Flowers", 20),
            Answer("Air freshener", 14),
            Answer("Clean laundry", 9),
        ],
    ),
    Board(
        "Name something you might forget when packing for a trip",
        [
            Answer("Charger or phone charger", 30),
            Answer("Toothbrush or toiletries", 25),
            Answer("Passport or ID", 20),
            Answer("Medication", 13),
            Answer("Underwear or socks", 8),
            Answer("Sunscreen", 4),
        ],
    ),
]
