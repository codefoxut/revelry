from __future__ import annotations

from app.game_engine.base import Command, Event, GameEngine
from app.games.two_truths_and_a_lie.commands import (
    CastVoteCommand,
    NextRoundCommand,
    RevealCommand,
    StartGameCommand,
    SubmitStatementsCommand,
)
from app.games.two_truths_and_a_lie.events import (
    GameOverEvent,
    PlayerVotedEvent,
    RevealedEvent,
    RoundStartedEvent,
    StatementsSubmittedEvent,
)
from app.games.two_truths_and_a_lie.phases import TWO_TRUTHS_TRANSITIONS, TwoTruthsPhase
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError
from app.platform.state_machine import StateMachine

_POINTS_CORRECT_GUESS = 100


class TwoTruthsGameEngine(GameEngine):
    def __init__(self, room_code: str) -> None:
        self._room_code = room_code
        self._state_machine = StateMachine(TwoTruthsPhase.LOBBY, TWO_TRUTHS_TRANSITIONS)
        self._player_order: list[str] = []
        self._storyteller_index: int = 0
        self._round_number: int = 0
        self._total_rounds: int = 0
        self._statements: list[str] | None = None
        self._lie_index: int | None = None  # never sent to clients before reveal
        self._votes: dict[str, int] = {}   # player_id -> choice_index
        self._correct_voters: list[str] = []
        self._scores: dict[str, int] = {}

    @property
    def _storyteller_id(self) -> str | None:
        if not self._player_order:
            return None
        return self._player_order[self._storyteller_index % len(self._player_order)]

    def _voter_ids(self) -> list[str]:
        return [p for p in self._player_order if p != self._storyteller_id]

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, SubmitStatementsCommand):
            return self._submit_statements(command)
        if isinstance(command, CastVoteCommand):
            return self._cast_vote(command)
        if isinstance(command, RevealCommand):
            return self._reveal(command)
        if isinstance(command, NextRoundCommand):
            return self._next_round(command)
        raise ValueError(f"Unsupported command: {command!r}")

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        self._player_order = list(command.active_player_ids)
        self._total_rounds = len(self._player_order)
        self._scores = {p: 0 for p in self._player_order}
        self._storyteller_index = 0
        self._round_number = 1
        self._statements = None
        self._lie_index = None
        self._votes = {}
        self._correct_voters = []
        self._state_machine.transition_to(TwoTruthsPhase.SUBMITTING)
        assert self._storyteller_id is not None
        return [RoundStartedEvent(storyteller_id=self._storyteller_id)]

    def _submit_statements(self, command: SubmitStatementsCommand) -> list[Event]:
        if self._state_machine.phase != TwoTruthsPhase.SUBMITTING:
            raise InvalidGameStateError("Statements can only be submitted during the submitting phase")
        if command.player_id != self._storyteller_id:
            raise PermissionDeniedError("Only the Storyteller can submit statements")
        if len(command.statements) != 3:
            raise InvalidGameStateError("Exactly 3 statements are required")
        if any(not s.strip() for s in command.statements):
            raise InvalidGameStateError("All 3 statements must be non-empty")
        if command.lie_index not in {0, 1, 2}:
            raise InvalidGameStateError("lie_index must be 0, 1, or 2")

        self._statements = list(command.statements)
        self._lie_index = command.lie_index
        self._votes = {}
        self._correct_voters = []
        self._state_machine.transition_to(TwoTruthsPhase.VOTING)
        return [StatementsSubmittedEvent(statements=self._statements)]

    def _cast_vote(self, command: CastVoteCommand) -> list[Event]:
        if self._state_machine.phase != TwoTruthsPhase.VOTING:
            raise InvalidGameStateError("Voting is not open right now")
        if command.player_id == self._storyteller_id:
            raise PermissionDeniedError("The Storyteller cannot vote — they already know the lie")
        if command.player_id not in self._player_order:
            raise PermissionDeniedError("Only participants can vote")
        if command.choice_index not in {0, 1, 2}:
            raise InvalidGameStateError("choice_index must be 0, 1, or 2")
        if command.player_id in self._votes:
            raise InvalidGameStateError("You have already voted this round")

        self._votes[command.player_id] = command.choice_index
        events: list[Event] = [PlayerVotedEvent(player_id=command.player_id)]

        if len(self._votes) >= len(self._voter_ids()):
            events.extend(self._do_reveal())

        return events

    def _reveal(self, command: RevealCommand) -> list[Event]:
        if self._state_machine.phase != TwoTruthsPhase.VOTING:
            raise InvalidGameStateError("Nothing to reveal right now")
        return self._do_reveal()

    def _do_reveal(self) -> list[Event]:
        assert self._lie_index is not None
        self._correct_voters = [p for p, v in self._votes.items() if v == self._lie_index]
        scores_delta = self._award_points()
        self._state_machine.transition_to(TwoTruthsPhase.REVEAL)
        return [
            RevealedEvent(
                lie_index=self._lie_index,
                correct_voters=list(self._correct_voters),
                scores_delta=scores_delta,
            )
        ]

    def _award_points(self) -> dict[str, int]:
        delta: dict[str, int] = {}
        storyteller_id = self._storyteller_id
        assert storyteller_id is not None

        for player_id in self._correct_voters:
            self._scores[player_id] = self._scores.get(player_id, 0) + _POINTS_CORRECT_GUESS
            delta[player_id] = _POINTS_CORRECT_GUESS

        storyteller_pts = self._storyteller_score()
        if storyteller_pts > 0:
            self._scores[storyteller_id] = self._scores.get(storyteller_id, 0) + storyteller_pts
            delta[storyteller_id] = storyteller_pts

        return delta

    def _storyteller_score(self) -> int:
        # Storyteller earns points for fooling guessers.
        # Formula: 100 * (wrong_guessers / total_guessers)
        # Example: 1 correct out of 3 guessers → 100 * 2/3 ≈ 66 for Storyteller.
        # More wrong guessers = higher fooled fraction = more Storyteller points.
        total = len(self._voter_ids())
        if total == 0:
            return 0
        wrong = total - len(self._correct_voters)
        return int(_POINTS_CORRECT_GUESS * wrong / total)

    def _next_round(self, command: NextRoundCommand) -> list[Event]:
        if self._state_machine.phase != TwoTruthsPhase.REVEAL:
            raise InvalidGameStateError("Reveal the current round before advancing")

        if self._round_number >= self._total_rounds:
            self._state_machine.transition_to(TwoTruthsPhase.GAME_OVER)
            return [GameOverEvent(scores=dict(self._scores))]

        self._storyteller_index += 1
        self._round_number += 1
        self._statements = None
        self._lie_index = None
        self._votes = {}
        self._correct_voters = []
        self._state_machine.transition_to(TwoTruthsPhase.SUBMITTING)
        assert self._storyteller_id is not None
        return [RoundStartedEvent(storyteller_id=self._storyteller_id)]

    def phase_snapshot(self) -> dict[str, object]:
        phase = self._state_machine.phase
        at_reveal = phase in (TwoTruthsPhase.REVEAL, TwoTruthsPhase.GAME_OVER)
        return {
            "phase": phase.value,
            "round_number": self._round_number,
            "total_rounds": self._total_rounds,
            "storyteller_id": self._storyteller_id,
            "statements": self._statements,
            "voted_count": len(self._votes),
            # lie_index is never sent before reveal — kept None until then
            "lie_index": self._lie_index if at_reveal else None,
            "correct_voters": list(self._correct_voters) if at_reveal else None,
            "scores": dict(self._scores),
        }
