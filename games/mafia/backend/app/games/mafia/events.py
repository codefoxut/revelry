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
