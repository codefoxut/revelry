from __future__ import annotations

import random
from typing import Literal

from app.game_engine.base import Command, Event, GameEngine
from app.games.family_feud.boards import BOARD_BANK, Board
from app.games.family_feud.commands import (
    BuzzInCommand,
    NextRoundCommand,
    RevealSlotCommand,
    StartGameCommand,
    StealMissCommand,
    StealRevealCommand,
    StrikeCommand,
)
from app.games.family_feud.events import (
    GameOverEvent,
    PlayerBuzzedEvent,
    QuestionShownEvent,
    RoundOverEvent,
    SlotRevealedEvent,
    StealPhaseEvent,
    StrikeEvent,
)
from app.games.family_feud.phases import FAMILY_FEUD_TRANSITIONS, FamilyFeudPhase
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError
from app.platform.state_machine import StateMachine

_ROUNDS_PER_GAME = 5
_MAX_STRIKES = 3


class FamilyFeudGameEngine(GameEngine):
    """Teams buzz in, the host judges answers against a hidden board.

    Team scoping (team_of dict) lives entirely inside this engine — the shared
    platform Room/Player model is never touched. Host-only command permission
    checks (reveal, strike, steal, next_round) live in GameSessionManager,
    which has access to Room.host_player_id.
    """

    def __init__(self, room_code: str) -> None:
        self._room_code = room_code
        self._state_machine = StateMachine(FamilyFeudPhase.LOBBY, FAMILY_FEUD_TRANSITIONS)
        self._boards: list[Board] = []
        self._round_index = -1
        self._team_of: dict[str, Literal["a", "b"]] = {}
        self._team_scores: dict[str, int] = {"a": 0, "b": 0}
        self._controlling_team: Literal["a", "b"] | None = None
        self._strikes = 0
        self._board_revealed: list[bool] = []

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, BuzzInCommand):
            return self._buzz_in(command)
        if isinstance(command, RevealSlotCommand):
            return self._reveal_slot(command)
        if isinstance(command, StrikeCommand):
            return self._strike(command)
        if isinstance(command, StealRevealCommand):
            return self._steal_reveal(command)
        if isinstance(command, StealMissCommand):
            return self._steal_miss(command)
        if isinstance(command, NextRoundCommand):
            return self._next_round(command)
        raise ValueError(f"Unsupported command: {command!r}")

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        self._team_of = dict(command.team_of)
        self._team_scores = {"a": 0, "b": 0}
        pool_size = min(len(BOARD_BANK), _ROUNDS_PER_GAME)
        self._boards = random.sample(BOARD_BANK, pool_size)
        self._round_index = 0
        self._controlling_team = None
        self._strikes = 0
        self._board_revealed = [False] * len(self._boards[0].answers)
        self._state_machine.transition_to(FamilyFeudPhase.QUESTION_OPEN)
        return [self._question_shown_event()]

    def _question_shown_event(self) -> QuestionShownEvent:
        board = self._boards[self._round_index]
        return QuestionShownEvent(
            round_number=self._round_index + 1,
            total_rounds=len(self._boards),
            prompt=board.prompt,
            answer_count=len(board.answers),
        )

    def _buzz_in(self, command: BuzzInCommand) -> list[Event]:
        if self._state_machine.phase != FamilyFeudPhase.QUESTION_OPEN:
            raise InvalidGameStateError("Buzzing isn't open right now")
        if command.player_id not in self._team_of:
            raise PermissionDeniedError("Only team members can buzz in")

        team = self._team_of[command.player_id]
        self._controlling_team = team
        self._strikes = 0
        self._state_machine.transition_to(FamilyFeudPhase.ANSWERING)
        return [PlayerBuzzedEvent(player_id=command.player_id, team=team)]

    def _current_board(self) -> Board:
        return self._boards[self._round_index]

    def _board_points_revealed(self) -> int:
        board = self._current_board()
        return sum(
            board.answers[i].points
            for i in range(len(board.answers))
            if self._board_revealed[i]
        )

    def _full_board_out(self) -> list[dict]:
        board = self._current_board()
        return [
            {"text": a.text, "points": a.points, "revealed": self._board_revealed[i]}
            for i, a in enumerate(board.answers)
        ]

    def _reveal_slot(self, command: RevealSlotCommand) -> list[Event]:
        if self._state_machine.phase != FamilyFeudPhase.ANSWERING:
            raise InvalidGameStateError("Not in answering phase")
        board = self._current_board()
        if not (0 <= command.slot_index < len(board.answers)):
            raise InvalidGameStateError(f"Slot index {command.slot_index} out of range")
        if self._board_revealed[command.slot_index]:
            raise InvalidGameStateError(f"Slot {command.slot_index} is already revealed")

        self._board_revealed[command.slot_index] = True
        answer = board.answers[command.slot_index]
        events: list[Event] = [
            SlotRevealedEvent(slot_index=command.slot_index, text=answer.text, points=answer.points)
        ]

        if all(self._board_revealed):
            assert self._controlling_team is not None
            points = self._board_points_revealed()
            self._team_scores[self._controlling_team] += points
            self._state_machine.transition_to(FamilyFeudPhase.ROUND_OVER)
            events.append(
                RoundOverEvent(
                    team_awarded=self._controlling_team,
                    points=points,
                    board=self._full_board_out(),
                )
            )

        return events

    def _strike(self, command: StrikeCommand) -> list[Event]:
        if self._state_machine.phase != FamilyFeudPhase.ANSWERING:
            raise InvalidGameStateError("Not in answering phase")
        assert self._controlling_team is not None

        self._strikes += 1
        events: list[Event] = [StrikeEvent(team=self._controlling_team, strikes=self._strikes)]

        if self._strikes >= _MAX_STRIKES:
            stealing_team: Literal["a", "b"] = "b" if self._controlling_team == "a" else "a"
            self._state_machine.transition_to(FamilyFeudPhase.STEAL)
            events.append(StealPhaseEvent(stealing_team=stealing_team))

        return events

    def _steal_reveal(self, command: StealRevealCommand) -> list[Event]:
        if self._state_machine.phase != FamilyFeudPhase.STEAL:
            raise InvalidGameStateError("Not in steal phase")
        board = self._current_board()
        if not (0 <= command.slot_index < len(board.answers)):
            raise InvalidGameStateError(f"Slot index {command.slot_index} out of range")
        if self._board_revealed[command.slot_index]:
            raise InvalidGameStateError(f"Slot {command.slot_index} is already revealed")

        self._board_revealed[command.slot_index] = True
        answer = board.answers[command.slot_index]
        assert self._controlling_team is not None
        stealing_team: Literal["a", "b"] = "b" if self._controlling_team == "a" else "a"
        points = self._board_points_revealed()
        self._team_scores[stealing_team] += points
        self._state_machine.transition_to(FamilyFeudPhase.ROUND_OVER)
        return [
            SlotRevealedEvent(slot_index=command.slot_index, text=answer.text, points=answer.points),
            RoundOverEvent(team_awarded=stealing_team, points=points, board=self._full_board_out()),
        ]

    def _steal_miss(self, command: StealMissCommand) -> list[Event]:
        if self._state_machine.phase != FamilyFeudPhase.STEAL:
            raise InvalidGameStateError("Not in steal phase")
        assert self._controlling_team is not None

        points = self._board_points_revealed()
        self._team_scores[self._controlling_team] += points
        self._state_machine.transition_to(FamilyFeudPhase.ROUND_OVER)
        return [
            RoundOverEvent(
                team_awarded=self._controlling_team,
                points=points,
                board=self._full_board_out(),
            )
        ]

    def _next_round(self, command: NextRoundCommand) -> list[Event]:
        if self._state_machine.phase != FamilyFeudPhase.ROUND_OVER:
            raise InvalidGameStateError("Can't advance: not in round_over phase")

        if self._round_index + 1 >= len(self._boards):
            self._state_machine.transition_to(FamilyFeudPhase.GAME_OVER)
            top_score = max(self._team_scores.values(), default=0)
            winners = [team for team, score in self._team_scores.items() if score == top_score]
            winning_team: Literal["a", "b"] | None = winners[0] if len(winners) == 1 else None  # type: ignore[assignment]
            return [GameOverEvent(team_scores=dict(self._team_scores), winning_team=winning_team)]

        self._round_index += 1
        self._controlling_team = None
        self._strikes = 0
        self._board_revealed = [False] * len(self._boards[self._round_index].answers)
        self._state_machine.transition_to(FamilyFeudPhase.QUESTION_OPEN)
        return [self._question_shown_event()]

    def phase_snapshot(self) -> dict[str, object]:
        phase = self._state_machine.phase
        board_obj = self._boards[self._round_index] if self._round_index >= 0 else None

        board_out: list[dict] = []
        if board_obj is not None:
            for i, answer in enumerate(board_obj.answers):
                if self._board_revealed[i]:
                    board_out.append({"text": answer.text, "points": answer.points, "revealed": True})
                else:
                    board_out.append({"text": None, "points": None, "revealed": False})

        return {
            "phase": phase.value,
            "round_number": self._round_index + 1 if self._round_index >= 0 else 0,
            "total_rounds": len(self._boards),
            "prompt": board_obj.prompt if board_obj is not None else None,
            "answer_count": len(board_obj.answers) if board_obj is not None else 0,
            "board": board_out,
            "controlling_team": self._controlling_team,
            "strikes": self._strikes,
            "team_scores": dict(self._team_scores),
            "team_of": dict(self._team_of),
        }
