from enum import Enum
from typing import Generic, TypeVar

PhaseT = TypeVar("PhaseT", bound=Enum)


class StateMachine(Generic[PhaseT]):
    """Generic finite state machine driving a game's phase transitions.

    Games define their own Phase enum and transition table (e.g. Mafia's
    Lobby -> RoleAssignment -> Night -> ... -> GameOver); this class only owns
    "what phase am I in" and "is this transition allowed". It has no
    Mafia-specific knowledge, so future games reuse it as-is.
    """

    def __init__(self, initial_phase: PhaseT, transitions: dict[PhaseT, set[PhaseT]]) -> None:
        self._phase = initial_phase
        self._transitions = transitions

    @property
    def phase(self) -> PhaseT:
        return self._phase

    def can_transition_to(self, target: PhaseT) -> bool:
        return target in self._transitions.get(self._phase, set())

    def transition_to(self, target: PhaseT) -> None:
        if not self.can_transition_to(target):
            raise ValueError(f"Illegal transition: {self._phase} -> {target}")
        self._phase = target
