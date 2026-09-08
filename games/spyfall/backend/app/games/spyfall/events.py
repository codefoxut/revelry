from app.game_engine.base import Event
from app.games.spyfall.phases import SpyfallPhase


class PhaseChangedEvent(Event):
    """Emitted whenever the engine's phase changes. The WS layer folds this
    into a full room_state rebroadcast rather than forwarding it verbatim —
    it still exists on the engine's contract so tests/future consumers can
    observe transitions without a WebSocket.
    """

    phase: SpyfallPhase
    round_number: int


class RoleAssignedEvent(Event):
    """A single player's own assignment. Unlike PhaseChangedEvent this is
    never broadcast — it's private information. `location`/`role` are both
    None exactly when `is_spy` is True.
    """

    player_id: str
    is_spy: bool
    location: str | None
    role: str | None


class VoteCastEvent(Event):
    """A single public vote for the suspected spy, cast during VOTING. Votes
    are open, so this is broadcast to the whole room as each one comes in.
    """

    player_id: str
    target_player_id: str


class PlayerRoleReveal(Event):
    """One player's final assignment. Only ever included on GameOverEvent —
    a role stops being private information once the game has ended."""

    player_id: str
    is_spy: bool
    role: str | None


class GameOverEvent(Event):
    """The game has ended, for one of three reasons: the spy correctly
    guessed the location (winning_side=spies, accused_player_id=None), the
    spy guessed wrong (winning_side=non_spies, accused_player_id=None), or a
    voting round resolved (accused_player_id set to whoever the room voted
    for, or None if the vote tied/had no consensus — either way the spy
    wins by evading capture).
    """

    winning_side: str
    location: str
    spy_player_ids: list[str]
    accused_player_id: str | None
    reveals: list[PlayerRoleReveal]
