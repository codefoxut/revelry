from __future__ import annotations

from app.game_engine.base import Event


class RoundStartedEvent(Event):
    storyteller_id: str


class StatementsSubmittedEvent(Event):
    statements: list[str]


class PlayerVotedEvent(Event):
    player_id: str


class RevealedEvent(Event):
    lie_index: int
    correct_voters: list[str]
    scores_delta: dict[str, int]


class GameOverEvent(Event):
    scores: dict[str, int]
