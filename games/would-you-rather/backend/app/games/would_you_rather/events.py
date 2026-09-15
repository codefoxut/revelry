from __future__ import annotations

from typing import Literal

from app.game_engine.base import Event


class QuestionShownEvent(Event):
    question_number: int
    total_questions: int
    option_a: str
    option_b: str


class PlayerVotedEvent(Event):
    player_id: str


class VotesRevealedEvent(Event):
    votes: dict[str, Literal["a", "b"]]


class GameOverEvent(Event):
    recap: list[dict]
