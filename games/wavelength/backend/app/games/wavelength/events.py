from __future__ import annotations

from app.game_engine.base import Event


class RoundStartedEvent(Event):
    """Emitted when a new round begins (start_game or next_round).
    Public — broadcast to all. No target_position here; that goes via private WS event.
    """

    psychic_id: str
    left_label: str
    right_label: str
    round_number: int


class ClueGivenEvent(Event):
    """Psychic has typed their clue (said it verbally, optionally typed it too)."""

    clue_text: str
    psychic_id: str


class PlayerGuessedEvent(Event):
    """A guesser has locked in their position. Only reveals count, not position."""

    player_id: str
    guessed_count: int


class RevealedEvent(Event):
    """Reveal phase: target, all guesses, and round points — broadcast to all."""

    target_position: float
    guesses: dict[str, float]
    points_awarded: dict[str, int]


class GameOverEvent(Event):
    """Final leaderboard after all rounds."""

    scores: dict[str, int]
