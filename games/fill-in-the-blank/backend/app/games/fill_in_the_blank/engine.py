from __future__ import annotations

import random
import uuid

from app.game_engine.base import Command, Event, GameEngine
from app.games.fill_in_the_blank.commands import (
    CastVoteCommand,
    NextPromptCommand,
    RevealCommand,
    StartGameCommand,
    StartVoteCommand,
    SubmitAnswerCommand,
)
from app.games.fill_in_the_blank.events import (
    GameOverEvent,
    PlayerSubmittedEvent,
    PlayerVotedEvent,
    PromptShownEvent,
    RoundOverEvent,
    SubmissionsRevealedEvent,
    VoteResultsEvent,
)
from app.games.fill_in_the_blank.phases import FILL_IN_THE_BLANK_TRANSITIONS, FillInTheBlankPhase
from app.games.fill_in_the_blank.prompts import PROMPTS
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError
from app.platform.state_machine import StateMachine

_POINTS_PER_VOTE = 100
_DEFAULT_TOTAL_QUESTIONS = 7

MIN_PLAYERS = 3


class FillInTheBlankGameEngine(GameEngine):
    def __init__(self, room_code: str) -> None:
        self._room_code = room_code
        self._state_machine = StateMachine(FillInTheBlankPhase.LOBBY, FILL_IN_THE_BLANK_TRANSITIONS)
        self._player_ids: list[str] = []
        self._question_number: int = 0
        self._total_questions: int = _DEFAULT_TOTAL_QUESTIONS
        self._prompts_queue: list[str] = []
        self._prompt: str | None = None
        # submission_id -> {"text": str, "author_id": str}
        self._submissions: dict[str, dict] = {}
        # submission_ids in shuffled order for display (author-blind)
        self._submission_order: list[str] = []
        # voter_id -> submission_id
        self._votes: dict[str, str] = {}
        self._scores: dict[str, int] = {}
        # Populated after compute_results
        self._results: list[dict] | None = None
        self._scores_delta: dict[str, int] = {}

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, SubmitAnswerCommand):
            return self._submit_answer(command)
        if isinstance(command, RevealCommand):
            return self._reveal(command)
        if isinstance(command, StartVoteCommand):
            return self._start_vote(command)
        if isinstance(command, CastVoteCommand):
            return self._cast_vote(command)
        if isinstance(command, NextPromptCommand):
            return self._next_prompt(command)
        raise ValueError(f"Unsupported command: {command!r}")

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        self._player_ids = list(command.active_player_ids)
        self._total_questions = min(_DEFAULT_TOTAL_QUESTIONS, len(PROMPTS))
        self._scores = {p: 0 for p in self._player_ids}
        self._prompts_queue = random.sample(PROMPTS, self._total_questions)
        self._question_number = 0
        return self._advance_to_next_prompt()

    def _advance_to_next_prompt(self) -> list[Event]:
        self._question_number += 1
        self._prompt = self._prompts_queue[self._question_number - 1]
        self._submissions = {}
        self._submission_order = []
        self._votes = {}
        self._results = None
        self._scores_delta = {}
        self._state_machine.transition_to(FillInTheBlankPhase.PROMPT_OPEN)
        return [
            PromptShownEvent(
                prompt=self._prompt,
                question_number=self._question_number,
                total_questions=self._total_questions,
            )
        ]

    def _submit_answer(self, command: SubmitAnswerCommand) -> list[Event]:
        if self._state_machine.phase != FillInTheBlankPhase.PROMPT_OPEN:
            raise InvalidGameStateError("Answers can only be submitted during prompt_open phase")
        if command.player_id not in self._player_ids:
            raise PermissionDeniedError("Only room players can submit answers")
        if any(info["author_id"] == command.player_id for info in self._submissions.values()):
            raise InvalidGameStateError("You have already submitted an answer this round")
        if not command.text.strip():
            raise InvalidGameStateError("Answer cannot be empty")

        submission_id = str(uuid.uuid4())
        self._submissions[submission_id] = {
            "text": command.text.strip(),
            "author_id": command.player_id,
        }
        return [PlayerSubmittedEvent(player_id=command.player_id)]

    def _reveal(self, command: RevealCommand) -> list[Event]:
        if self._state_machine.phase != FillInTheBlankPhase.PROMPT_OPEN:
            raise InvalidGameStateError("Nothing to reveal right now")
        self._submission_order = list(self._submissions.keys())
        random.shuffle(self._submission_order)
        self._state_machine.transition_to(FillInTheBlankPhase.SUBMISSIONS_REVEALED)
        return [
            SubmissionsRevealedEvent(
                submissions=[
                    {"submission_id": sid, "text": self._submissions[sid]["text"]}
                    for sid in self._submission_order
                ]
            )
        ]

    def _start_vote(self, command: StartVoteCommand) -> list[Event]:
        if self._state_machine.phase != FillInTheBlankPhase.SUBMISSIONS_REVEALED:
            raise InvalidGameStateError("Voting can only start after submissions are revealed")
        self._votes = {}
        self._state_machine.transition_to(FillInTheBlankPhase.VOTING)
        return []

    def _cast_vote(self, command: CastVoteCommand) -> list[Event]:
        if self._state_machine.phase != FillInTheBlankPhase.VOTING:
            raise InvalidGameStateError("Voting is not open right now")
        if command.player_id not in self._player_ids:
            raise PermissionDeniedError("Only room players can vote")
        if command.submission_id not in self._submissions:
            raise InvalidGameStateError("Unknown submission_id")
        # Server-side self-vote rejection — critical: must be enforced here regardless of client behaviour
        if self._submissions[command.submission_id]["author_id"] == command.player_id:
            raise PermissionDeniedError("You cannot vote for your own submission")
        if command.player_id in self._votes:
            raise InvalidGameStateError("You have already voted this round")

        self._votes[command.player_id] = command.submission_id
        return [PlayerVotedEvent(player_id=command.player_id)]

    def _next_prompt(self, command: NextPromptCommand) -> list[Event]:
        if self._state_machine.phase == FillInTheBlankPhase.VOTING:
            return self._compute_results_and_advance()
        if self._state_machine.phase == FillInTheBlankPhase.RESULTS:
            return self._advance_from_results()
        raise InvalidGameStateError("Can only advance from voting or results phase")

    def _compute_results_and_advance(self) -> list[Event]:
        vote_counts: dict[str, int] = {sid: 0 for sid in self._submissions}
        for voted_sid in self._votes.values():
            vote_counts[voted_sid] = vote_counts.get(voted_sid, 0) + 1

        results = [
            {
                "submission_id": sid,
                "text": self._submissions[sid]["text"],
                "author_id": self._submissions[sid]["author_id"],
                "votes": vote_counts.get(sid, 0),
            }
            for sid in self._submission_order
        ]
        self._results = results

        # Every tied author gets full points (100 per vote received)
        scores_delta: dict[str, int] = {}
        for entry in results:
            if entry["votes"] > 0:
                author = entry["author_id"]
                pts = entry["votes"] * _POINTS_PER_VOTE
                self._scores[author] = self._scores.get(author, 0) + pts
                scores_delta[author] = scores_delta.get(author, 0) + pts
        self._scores_delta = scores_delta

        self._state_machine.transition_to(FillInTheBlankPhase.RESULTS)
        return [
            VoteResultsEvent(results=list(results)),
            RoundOverEvent(scores_delta=scores_delta),
        ]

    def _advance_from_results(self) -> list[Event]:
        if self._question_number >= self._total_questions:
            self._state_machine.transition_to(FillInTheBlankPhase.GAME_OVER)
            return [GameOverEvent(scores=dict(self._scores))]
        return self._advance_to_next_prompt()

    def phase_snapshot(self) -> dict[str, object]:
        phase = self._state_machine.phase
        at_results = phase in (FillInTheBlankPhase.RESULTS, FillInTheBlankPhase.GAME_OVER)

        submissions: list[dict] | None = None
        if phase in (
            FillInTheBlankPhase.SUBMISSIONS_REVEALED,
            FillInTheBlankPhase.VOTING,
            FillInTheBlankPhase.RESULTS,
        ):
            # author_id intentionally absent — only revealed via results field in RESULTS phase
            submissions = [
                {"submission_id": sid, "text": self._submissions[sid]["text"]}
                for sid in self._submission_order
            ]

        return {
            "phase": phase.value,
            "question_number": self._question_number,
            "total_questions": self._total_questions,
            "prompt": self._prompt,
            "submitted_count": len(self._submissions),
            "submissions": submissions,
            "voted_count": len(self._votes),
            "results": self._results if at_results else None,
            "scores": dict(self._scores),
        }
