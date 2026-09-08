from __future__ import annotations

from app.game_engine.base import Event


class QuestionShownEvent(Event):
    question_number: int
    total_questions: int
    category: str
    question: str


class PlayerBuzzedEvent(Event):
    player_id: str


class AnswerJudgedEvent(Event):
    player_id: str
    correct: bool
    score_delta: int


class AnswerRevealedEvent(Event):
    answer: str


class GameOverEvent(Event):
    scores: dict[str, int]
    winner_id: str | None
