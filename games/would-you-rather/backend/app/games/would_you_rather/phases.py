from __future__ import annotations

from enum import Enum


class Phase(str, Enum):
    LOBBY = "lobby"
    QUESTION_OPEN = "question_open"
    REVEALED = "revealed"
    GAME_OVER = "game_over"


WOULD_YOU_RATHER_TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.LOBBY: {Phase.QUESTION_OPEN},
    Phase.QUESTION_OPEN: {Phase.REVEALED},
    Phase.REVEALED: {Phase.QUESTION_OPEN, Phase.GAME_OVER},
    Phase.GAME_OVER: set(),
}
