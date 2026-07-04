from enum import Enum


class MafiaPhase(str, Enum):
    """Mafia's own phase sequence, driven by the generic StateMachine."""

    LOBBY = "lobby"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    ELIMINATION = "elimination"
    GAME_OVER = "game_over"


# NIGHT -> GAME_OVER: a night kill can end the game immediately (e.g. the
# mafia's kill reaches parity with the town) without waiting for a day/vote
# cycle that no longer matters.
# ELIMINATION -> GAME_OVER: the win-check that runs after a day's lynch.
MAFIA_TRANSITIONS: dict[MafiaPhase, set[MafiaPhase]] = {
    MafiaPhase.LOBBY: {MafiaPhase.NIGHT},
    MafiaPhase.NIGHT: {MafiaPhase.DAY, MafiaPhase.GAME_OVER},
    MafiaPhase.DAY: {MafiaPhase.VOTING},
    MafiaPhase.VOTING: {MafiaPhase.ELIMINATION},
    MafiaPhase.ELIMINATION: {MafiaPhase.NIGHT, MafiaPhase.GAME_OVER},
    MafiaPhase.GAME_OVER: set(),
}
