from __future__ import annotations

from app.game_engine.base import Command


class StartGameCommand(Command):
    active_player_ids: list[str]
    total_rounds: int = 8


class GiveClueCommand(Command):
    """Psychic-only: optionally types their verbal clue and advances to GUESSING."""

    clue_text: str = ""


class SubmitGuessCommand(Command):
    """Non-psychic: lock in a position on the spectrum (0–100)."""

    position: float


class RevealCommand(Command):
    """Psychic or host forces advance from GUESSING to REVEAL."""


class NextRoundCommand(Command):
    """Advance from REVEAL to the next round (or GAME_OVER if all rounds done)."""
