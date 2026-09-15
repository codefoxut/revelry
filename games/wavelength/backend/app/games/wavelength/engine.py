from __future__ import annotations

import random

from app.game_engine.base import Command, Event, GameEngine
from app.games.wavelength.commands import (
    GiveClueCommand,
    NextRoundCommand,
    RevealCommand,
    StartGameCommand,
    SubmitGuessCommand,
)
from app.games.wavelength.events import (
    ClueGivenEvent,
    GameOverEvent,
    PlayerGuessedEvent,
    RevealedEvent,
    RoundStartedEvent,
)
from app.games.wavelength.phases import WAVELENGTH_TRANSITIONS, Phase
from app.games.wavelength.spectrums import SPECTRUMS
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError
from app.platform.state_machine import StateMachine


def _score_for_distance(distance: float) -> int:
    """Scoring bands: closer to the target = more points."""
    if distance <= 2:
        return 4
    if distance <= 6:
        return 3
    if distance <= 12:
        return 2
    if distance <= 20:
        return 1
    return 0


class WavelengthEngine(GameEngine):
    """Pure game-rules for Wavelength.

    Each round: one Psychic sees a secret target position on a spectrum
    (0–100); they give a one-word/short clue out loud; guessers drag a slider
    to guess the position. Points scale with how close each guesser lands.
    Psychic earns the highest guesser's score that round.

    Psychic scoring rule: Psychic gets points equal to the single closest
    guesser's score for that round. If no guessers submitted, Psychic gets 0.
    """

    def __init__(self, room_code: str) -> None:
        self._room_code = room_code
        self._state_machine = StateMachine(Phase.LOBBY, WAVELENGTH_TRANSITIONS)
        self._player_order: list[str] = []
        self._psychic_index: int = 0
        self._round_number: int = 0
        self._total_rounds: int = 8
        self._left_label: str = ""
        self._right_label: str = ""
        self._target_position: float = 0.0
        self._clue_text: str | None = None
        self._guesses: dict[str, float] = {}
        self._round_points: dict[str, int] = {}
        self._scores: dict[str, int] = {}

    @property
    def _current_psychic_id(self) -> str | None:
        if not self._player_order:
            return None
        return self._player_order[self._psychic_index % len(self._player_order)]

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, GiveClueCommand):
            return self._give_clue(command)
        if isinstance(command, SubmitGuessCommand):
            return self._submit_guess(command)
        if isinstance(command, RevealCommand):
            return self._reveal(command)
        if isinstance(command, NextRoundCommand):
            return self._next_round(command)
        raise ValueError(f"Unhandled command: {command!r}")

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        player_ids = list(command.active_player_ids)
        random.shuffle(player_ids)
        self._player_order = player_ids
        self._psychic_index = 0
        self._total_rounds = command.total_rounds
        self._scores = {pid: 0 for pid in player_ids}
        return self._begin_round()

    def _begin_round(self) -> list[Event]:
        self._round_number += 1
        spectrum = random.choice(SPECTRUMS)
        self._left_label = spectrum["left"]
        self._right_label = spectrum["right"]
        self._target_position = random.uniform(5.0, 95.0)
        self._clue_text = None
        self._guesses = {}
        self._round_points = {}
        self._state_machine.transition_to(Phase.CLUE_GIVING)
        return [
            RoundStartedEvent(
                psychic_id=self._current_psychic_id,  # type: ignore[arg-type]
                left_label=self._left_label,
                right_label=self._right_label,
                round_number=self._round_number,
            )
        ]

    def _give_clue(self, command: GiveClueCommand) -> list[Event]:
        if self._state_machine.phase != Phase.CLUE_GIVING:
            raise InvalidGameStateError("Can only give a clue during the clue-giving phase")
        if command.player_id != self._current_psychic_id:
            raise PermissionDeniedError("Only the Psychic can give the clue")
        self._clue_text = command.clue_text.strip() or None
        self._state_machine.transition_to(Phase.GUESSING)
        return [ClueGivenEvent(clue_text=self._clue_text or "", psychic_id=command.player_id)]

    def _submit_guess(self, command: SubmitGuessCommand) -> list[Event]:
        if self._state_machine.phase != Phase.GUESSING:
            raise InvalidGameStateError("Can only submit a guess during the guessing phase")
        if command.player_id == self._current_psychic_id:
            raise PermissionDeniedError("The Psychic cannot guess their own round")
        if not (0.0 <= command.position <= 100.0):
            raise InvalidGameStateError("Position must be between 0 and 100")

        self._guesses[command.player_id] = command.position
        guessed_count = len(self._guesses)

        non_psychic_count = len(self._player_order) - 1
        events: list[Event] = [PlayerGuessedEvent(player_id=command.player_id, guessed_count=guessed_count)]

        if guessed_count >= non_psychic_count:
            events.extend(self._do_reveal())

        return events

    def _reveal(self, command: RevealCommand) -> list[Event]:
        if self._state_machine.phase != Phase.GUESSING:
            raise InvalidGameStateError("Can only force reveal during the guessing phase")
        if command.player_id != self._current_psychic_id:
            raise PermissionDeniedError("Only the Psychic can force reveal")
        return self._do_reveal()

    def _do_reveal(self) -> list[Event]:
        self._round_points = {}
        for player_id, position in self._guesses.items():
            distance = abs(position - self._target_position)
            self._round_points[player_id] = _score_for_distance(distance)

        psychic_id = self._current_psychic_id
        if self._round_points:
            psychic_points = max(self._round_points.values())
        else:
            psychic_points = 0

        for player_id, pts in self._round_points.items():
            self._scores[player_id] = self._scores.get(player_id, 0) + pts
        if psychic_id:
            self._scores[psychic_id] = self._scores.get(psychic_id, 0) + psychic_points
            self._round_points[psychic_id] = psychic_points

        self._state_machine.transition_to(Phase.REVEAL)
        return [
            RevealedEvent(
                target_position=self._target_position,
                guesses=dict(self._guesses),
                points_awarded=dict(self._round_points),
            )
        ]

    def _next_round(self, command: NextRoundCommand) -> list[Event]:
        if self._state_machine.phase != Phase.REVEAL:
            raise InvalidGameStateError("Can only advance to next round from the reveal phase")

        self._psychic_index += 1

        if self._round_number >= self._total_rounds:
            self._state_machine.transition_to(Phase.GAME_OVER)
            return [GameOverEvent(scores=dict(self._scores))]

        return self._begin_round()

    def phase_snapshot(self) -> dict[str, object]:
        phase = self._state_machine.phase
        in_reveal = phase == Phase.REVEAL

        return {
            "phase": phase.value,
            "round_number": self._round_number,
            "total_rounds": self._total_rounds,
            "psychic_id": self._current_psychic_id,
            "left_label": self._left_label,
            "right_label": self._right_label,
            # target_position is only included during REVEAL (secret before that)
            "target_position": self._target_position if in_reveal else None,
            "clue_text": self._clue_text,
            "guessed_count": len(self._guesses),
            "guesses": dict(self._guesses) if in_reveal else None,
            "points_awarded": dict(self._round_points) if in_reveal else None,
            "scores": dict(self._scores),
        }

    def get_target_position(self, player_id: str) -> float | None:
        """Returns the target only to the current Psychic during active (non-reveal) phases.

        The None return is the guard — dispatcher only sends PsychicTargetEvent when not None.
        During REVEAL, target is already in phase_snapshot (public by then), so no private event needed.
        """
        phase = self._state_machine.phase
        if phase not in (Phase.CLUE_GIVING, Phase.GUESSING):
            return None
        if player_id != self._current_psychic_id:
            return None
        return self._target_position
