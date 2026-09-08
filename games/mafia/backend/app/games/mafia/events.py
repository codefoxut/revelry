from app.game_engine.base import Event
from app.games.mafia.phases import MafiaPhase


class PhaseChangedEvent(Event):
    """Emitted whenever the engine's phase changes. The WS layer folds this
    into a full room_state rebroadcast rather than forwarding it verbatim
    (same "broadcast a fresh snapshot" convention as the lobby commands) —
    it still exists on the engine's contract so tests/future consumers
    (bots, simulations) can observe transitions without a WebSocket.
    """

    phase: MafiaPhase
    round_number: int


class RoleAssignedEvent(Event):
    """A single player's own role assignment. Unlike PhaseChangedEvent this
    is never broadcast — the WS layer must deliver each one only to the
    player it names, since a role is private information.
    """

    player_id: str
    role_key: str
    role_display_name: str
    team: str
    description: str
    acts_at_night: bool
    allow_self_target: bool


class InvestigationResultEvent(Event):
    """The detective's own investigation result — private, delivered only
    to the detective who submitted the action.
    """

    player_id: str
    target_player_id: str
    team: str


class NightResultEvent(Event):
    """Public announcement of who (if anyone) died overnight. Never says
    who did what — just the outcome. A list since more than one kill source
    (mafia, vigilante, serial killer) can resolve in the same night."""

    eliminated_player_ids: list[str]


class EliminationResultEvent(Event):
    """Public announcement of who (if anyone) the town voted out."""

    eliminated_player_id: str | None


class PlayerRoleReveal(Event):
    """One player's final role. Only ever included on `GameOverEvent` — a
    role stops being private information once the game has ended.
    """

    player_id: str
    role_key: str
    role_display_name: str
    team: str


class GameOverEvent(Event):
    """The game has ended. `winning_team` is a Team value. `roles` reveals
    every player's role now that the game is over, so every screen can
    render a final summary rather than just the winning team."""

    winning_team: str
    roles: list[PlayerRoleReveal]


class MafiaPick(Event):
    """One living mafia player's current night-action state."""

    player_id: str
    target_player_id: str | None
    locked: bool


class MafiaTargetsUpdatedEvent(Event):
    """Live snapshot of every living mafia player's current night pick.
    Mafia-team eyes only — the WS layer must never broadcast this
    room-wide.
    """

    picks: list[MafiaPick]


class MayorRevealedEvent(Event):
    """Public announcement that a Mayor has revealed and now votes with
    doubled weight."""

    player_id: str


class TerroristBombStatusEvent(Event):
    """The Terrorist's own bomb state after a night resolves — private,
    delivered only to the Terrorist. Lets their UI show "bomb pending on
    X" or "no bomb" going into the next round.
    """

    player_id: str
    pending: bool
    target_player_id: str | None
