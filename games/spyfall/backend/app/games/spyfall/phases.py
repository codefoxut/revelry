from enum import Enum


class SpyfallPhase(str, Enum):
    """Spyfall's own phase sequence, driven by the generic StateMachine.
    Unlike Mafia, this is a single-round game — there's no night/day cycle
    to repeat, so ELIMINATION -> back-to-NIGHT-style loops don't exist here.
    """

    LOBBY = "lobby"
    DISCUSSION = "discussion"
    VOTING = "voting"
    GAME_OVER = "game_over"


# DISCUSSION -> GAME_OVER: the spy can guess the location at any time during
# discussion, ending the game immediately without a vote.
# VOTING -> GAME_OVER: every voting round ends the game outright (a correct
# accusation, a wrong one, or a tied/no-consensus vote all resolve a winner —
# see engine.py's `_resolve_voting`), there is no "vote failed, try again."
SPYFALL_TRANSITIONS: dict[SpyfallPhase, set[SpyfallPhase]] = {
    SpyfallPhase.LOBBY: {SpyfallPhase.DISCUSSION},
    SpyfallPhase.DISCUSSION: {SpyfallPhase.VOTING, SpyfallPhase.GAME_OVER},
    SpyfallPhase.VOTING: {SpyfallPhase.GAME_OVER},
    SpyfallPhase.GAME_OVER: set(),
}
