from enum import Enum


class FillInTheBlankPhase(str, Enum):
    LOBBY = "lobby"
    PROMPT_OPEN = "prompt_open"
    SUBMISSIONS_REVEALED = "submissions_revealed"
    VOTING = "voting"
    RESULTS = "results"
    GAME_OVER = "game_over"


FILL_IN_THE_BLANK_TRANSITIONS: dict[FillInTheBlankPhase, set[FillInTheBlankPhase]] = {
    FillInTheBlankPhase.LOBBY: {FillInTheBlankPhase.PROMPT_OPEN},
    FillInTheBlankPhase.PROMPT_OPEN: {FillInTheBlankPhase.SUBMISSIONS_REVEALED},
    FillInTheBlankPhase.SUBMISSIONS_REVEALED: {FillInTheBlankPhase.VOTING},
    FillInTheBlankPhase.VOTING: {FillInTheBlankPhase.RESULTS},
    FillInTheBlankPhase.RESULTS: {FillInTheBlankPhase.PROMPT_OPEN, FillInTheBlankPhase.GAME_OVER},
    FillInTheBlankPhase.GAME_OVER: set(),
}
