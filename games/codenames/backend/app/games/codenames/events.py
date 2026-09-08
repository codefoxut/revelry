from __future__ import annotations

from app.game_engine.base import Event
from app.games.codenames.board import CardColor, Role, Team


class TeamAssignedEvent(Event):
    """A player's own team + role, sent only to that player (once at game
    start, and again on reconnect) — never broadcast to the room."""

    player_id: str
    team: Team
    role: Role


class ClueGivenEvent(Event):
    team: Team
    word: str
    number: int


class CardRevealedEvent(Event):
    card_index: int
    word: str
    color: CardColor
    guessed_by: str


class GameOverEvent(Event):
    winning_side: Team
    reason: str
    colors: list[CardColor]
