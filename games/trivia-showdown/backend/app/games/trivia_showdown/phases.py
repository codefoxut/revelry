from enum import Enum


class TriviaPhase(str, Enum):
    LOBBY = "lobby"
    QUESTION_OPEN = "question_open"
    ANSWERING = "answering"
    REVEALED = "revealed"
    GAME_OVER = "game_over"


TRIVIA_TRANSITIONS: dict[TriviaPhase, set[TriviaPhase]] = {
    TriviaPhase.LOBBY: {TriviaPhase.QUESTION_OPEN},
    TriviaPhase.QUESTION_OPEN: {TriviaPhase.ANSWERING, TriviaPhase.REVEALED},
    TriviaPhase.ANSWERING: {TriviaPhase.QUESTION_OPEN, TriviaPhase.REVEALED},
    TriviaPhase.REVEALED: {TriviaPhase.QUESTION_OPEN, TriviaPhase.GAME_OVER},
    TriviaPhase.GAME_OVER: set(),
}
