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
