from __future__ import annotations

from typing import Literal

from app.game_engine.base import Event


class QuestionShownEvent(Event):
    round_number: int
    total_rounds: int
    prompt: str
    answer_count: int


class PlayerBuzzedEvent(Event):
    player_id: str
    team: Literal["a", "b"]


class SlotRevealedEvent(Event):
    slot_index: int
    text: str
    points: int


class StrikeEvent(Event):
    team: Literal["a", "b"]
    strikes: int


class StealPhaseEvent(Event):
    stealing_team: Literal["a", "b"]


class RoundOverEvent(Event):
    team_awarded: Literal["a", "b"] | None
    points: int
    board: list[dict]


class GameOverEvent(Event):
    team_scores: dict[str, int]
    winning_team: Literal["a", "b"] | None = None
