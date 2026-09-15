from enum import Enum


class TwoTruthsPhase(str, Enum):
    LOBBY = "lobby"
    SUBMITTING = "submitting"
    VOTING = "voting"
    REVEAL = "reveal"
    GAME_OVER = "game_over"


TWO_TRUTHS_TRANSITIONS: dict[TwoTruthsPhase, set[TwoTruthsPhase]] = {
    TwoTruthsPhase.LOBBY: {TwoTruthsPhase.SUBMITTING},
    TwoTruthsPhase.SUBMITTING: {TwoTruthsPhase.VOTING},
    TwoTruthsPhase.VOTING: {TwoTruthsPhase.REVEAL},
    TwoTruthsPhase.REVEAL: {TwoTruthsPhase.SUBMITTING, TwoTruthsPhase.GAME_OVER},
    TwoTruthsPhase.GAME_OVER: set(),
}
