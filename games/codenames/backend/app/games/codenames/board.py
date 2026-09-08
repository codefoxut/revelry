from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

BOARD_SIZE = 25
_STARTING_TEAM_COUNT = 9
_SECOND_TEAM_COUNT = 8
_NEUTRAL_COUNT = 7
_ASSASSIN_COUNT = 1


class Team(str, Enum):
    RED = "red"
    BLUE = "blue"


class Role(str, Enum):
    SPYMASTER = "spymaster"
    GUESSER = "guesser"


class CardColor(str, Enum):
    RED = "red"
    BLUE = "blue"
    NEUTRAL = "neutral"
    ASSASSIN = "assassin"


@dataclass
class Card:
    word: str
    color: CardColor
    revealed: bool = False


def other_team(team: Team) -> Team:
    return Team.BLUE if team == Team.RED else Team.RED


def build_board(words: list[str], starting_team: Team) -> list[Card]:
    """Assemble a shuffled 25-card board.

    The starting team gets one extra word (9 vs 8) to offset the advantage
    of going second — the standard Codenames distribution.
    """
    if len(words) != BOARD_SIZE:
        raise ValueError(f"build_board needs exactly {BOARD_SIZE} words, got {len(words)}")

    colors = (
        [CardColor(starting_team.value)] * _STARTING_TEAM_COUNT
        + [CardColor(other_team(starting_team).value)] * _SECOND_TEAM_COUNT
        + [CardColor.NEUTRAL] * _NEUTRAL_COUNT
        + [CardColor.ASSASSIN] * _ASSASSIN_COUNT
    )
    random.shuffle(colors)
    return [Card(word=word, color=color) for word, color in zip(words, colors)]
