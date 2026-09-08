from enum import Enum


class CodenamesPhase(str, Enum):
    """Unlike Mafia/Spyfall's linear phase progression, Codenames alternates
    back and forth between the two teams' turns until someone wins.
    """

    LOBBY = "lobby"
    RED_TURN = "red_turn"
    BLUE_TURN = "blue_turn"
    GAME_OVER = "game_over"


CODENAMES_TRANSITIONS: dict[CodenamesPhase, set[CodenamesPhase]] = {
    CodenamesPhase.LOBBY: {CodenamesPhase.RED_TURN, CodenamesPhase.BLUE_TURN},
    CodenamesPhase.RED_TURN: {CodenamesPhase.BLUE_TURN, CodenamesPhase.GAME_OVER},
    CodenamesPhase.BLUE_TURN: {CodenamesPhase.RED_TURN, CodenamesPhase.GAME_OVER},
    CodenamesPhase.GAME_OVER: set(),
}
