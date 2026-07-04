from enum import Enum


class MafiaPhase(str, Enum):
    """Mafia's own phase sequence, driven by the generic StateMachine.

    Role actions/voting/win-checking are later steps (10/11) — this step
    only owns legal phase transitions.
    """

    LOBBY = "lobby"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    ELIMINATION = "elimination"
    GAME_OVER = "game_over"


# ELIMINATION -> GAME_OVER is structurally legal here, but nothing drives
# that transition yet — step 11's win-check decides NIGHT vs GAME_OVER.
MAFIA_TRANSITIONS: dict[MafiaPhase, set[MafiaPhase]] = {
    MafiaPhase.LOBBY: {MafiaPhase.NIGHT},
    MafiaPhase.NIGHT: {MafiaPhase.DAY},
    MafiaPhase.DAY: {MafiaPhase.VOTING},
    MafiaPhase.VOTING: {MafiaPhase.ELIMINATION},
    MafiaPhase.ELIMINATION: {MafiaPhase.NIGHT, MafiaPhase.GAME_OVER},
    MafiaPhase.GAME_OVER: set(),
}
