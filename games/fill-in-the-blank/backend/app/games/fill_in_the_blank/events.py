from __future__ import annotations

from app.game_engine.base import Event


class PromptShownEvent(Event):
    prompt: str
    question_number: int
    total_questions: int


class PlayerSubmittedEvent(Event):
    player_id: str


class SubmissionsRevealedEvent(Event):
    # [{submission_id, text}] only — author_id intentionally omitted
    submissions: list[dict]


class PlayerVotedEvent(Event):
    player_id: str


class VoteResultsEvent(Event):
    # [{submission_id, text, author_id, votes}] — author revealed for first time
    results: list[dict]


class RoundOverEvent(Event):
    scores_delta: dict[str, int]


class GameOverEvent(Event):
    scores: dict[str, int]
