from __future__ import annotations

import random
from typing import Literal

from app.game_engine.base import Command, Event, GameEngine
from app.games.would_you_rather.commands import (
    NextQuestionCommand,
    RevealCommand,
    StartGameCommand,
    SubmitVoteCommand,
)
from app.games.would_you_rather.events import (
    GameOverEvent,
    PlayerVotedEvent,
    QuestionShownEvent,
    VotesRevealedEvent,
)
from app.games.would_you_rather.phases import WOULD_YOU_RATHER_TRANSITIONS, Phase
from app.games.would_you_rather.prompts import PROMPT_BANK, Prompt
from app.platform.exceptions import InvalidGameStateError
from app.platform.state_machine import StateMachine

_QUESTIONS_PER_GAME = 10


class WouldYouRatherEngine(GameEngine):
    """Social voting game: host reads A/B prompts, players vote, reveal the split."""

    def __init__(self, room_code: str) -> None:
        self._room_code = room_code
        self._state_machine = StateMachine(Phase.LOBBY, WOULD_YOU_RATHER_TRANSITIONS)
        self._prompts: list[Prompt] = []
        self._question_index: int = -1
        self._player_ids: list[str] = []
        self._votes: dict[str, Literal["a", "b"]] = {}
        self._recap: list[dict] = []

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, SubmitVoteCommand):
            return self._submit_vote(command)
        if isinstance(command, RevealCommand):
            return self._reveal(command)
        if isinstance(command, NextQuestionCommand):
            return self._next_question(command)
        raise ValueError(f"Unhandled command: {command!r}")

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        self._player_ids = list(command.active_player_ids)
        pool_size = min(len(PROMPT_BANK), _QUESTIONS_PER_GAME)
        self._prompts = random.sample(PROMPT_BANK, pool_size)
        self._question_index = 0
        self._votes = {}
        self._recap = []
        self._state_machine.transition_to(Phase.QUESTION_OPEN)
        return [self._question_shown_event()]

    def _question_shown_event(self) -> QuestionShownEvent:
        prompt = self._prompts[self._question_index]
        return QuestionShownEvent(
            question_number=self._question_index + 1,
            total_questions=len(self._prompts),
            option_a=prompt.option_a,
            option_b=prompt.option_b,
        )

    def _submit_vote(self, command: SubmitVoteCommand) -> list[Event]:
        if self._state_machine.phase != Phase.QUESTION_OPEN:
            raise InvalidGameStateError("Voting is not open right now")
        self._votes[command.player_id] = command.choice
        return [PlayerVotedEvent(player_id=command.player_id)]

    def _reveal(self, command: RevealCommand) -> list[Event]:
        if self._state_machine.phase != Phase.QUESTION_OPEN:
            raise InvalidGameStateError("Can only reveal during voting phase")
        prompt = self._prompts[self._question_index]
        self._recap.append({
            "option_a": prompt.option_a,
            "option_b": prompt.option_b,
            "votes": dict(self._votes),
        })
        self._state_machine.transition_to(Phase.REVEALED)
        return [VotesRevealedEvent(votes=dict(self._votes))]

    def _next_question(self, command: NextQuestionCommand) -> list[Event]:
        if self._state_machine.phase != Phase.REVEALED:
            raise InvalidGameStateError("Reveal the current question before moving on")
        self._votes = {}

        if self._question_index + 1 >= len(self._prompts):
            self._state_machine.transition_to(Phase.GAME_OVER)
            return [GameOverEvent(recap=list(self._recap))]

        self._question_index += 1
        self._state_machine.transition_to(Phase.QUESTION_OPEN)
        return [self._question_shown_event()]

    def phase_snapshot(self) -> dict[str, object]:
        phase = self._state_machine.phase
        prompt = (
            self._prompts[self._question_index]
            if 0 <= self._question_index < len(self._prompts)
            else None
        )
        return {
            "phase": phase.value,
            "round_number": self._question_index + 1 if prompt else 0,
            "total_questions": len(self._prompts),
            "option_a": prompt.option_a if prompt else None,
            "option_b": prompt.option_b if prompt else None,
            "voted": sorted(self._votes.keys()),
            "revealed_votes": dict(self._votes) if phase == Phase.REVEALED else None,
            "recap": list(self._recap) if phase == Phase.GAME_OVER else None,
        }
