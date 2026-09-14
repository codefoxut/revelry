from enum import Enum


class Phase(str, Enum):
    LOBBY = "lobby"
    CLUE_GIVING = "clue_giving"
    GUESSING = "guessing"
    REVEAL = "reveal"
    GAME_OVER = "game_over"


WAVELENGTH_TRANSITIONS: dict[Phase, set[Phase]] = {
    Phase.LOBBY: {Phase.CLUE_GIVING},
    Phase.CLUE_GIVING: {Phase.GUESSING},
    Phase.GUESSING: {Phase.REVEAL},
    Phase.REVEAL: {Phase.CLUE_GIVING, Phase.GAME_OVER},
    Phase.GAME_OVER: set(),
}
