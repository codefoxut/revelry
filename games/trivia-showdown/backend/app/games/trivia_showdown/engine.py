from __future__ import annotations

import random

from app.game_engine.base import Command, Event, GameEngine
from app.games.trivia_showdown.commands import (
    BuzzInCommand,
    JudgeAnswerCommand,
    NextQuestionCommand,
    RevealCommand,
    StartGameCommand,
)
from app.games.trivia_showdown.events import (
    AnswerJudgedEvent,
    AnswerRevealedEvent,
    GameOverEvent,
    PlayerBuzzedEvent,
    QuestionShownEvent,
)
from app.games.trivia_showdown.phases import TRIVIA_TRANSITIONS, TriviaPhase
from app.games.trivia_showdown.questions import QUESTION_BANK, Question
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError
from app.platform.state_machine import StateMachine

_QUESTIONS_PER_GAME = 10
_POINTS_PER_CORRECT = 100


class TriviaShowdownGameEngine(GameEngine):
    """Buzz-in trivia: the host reads/judges, contestants race to buzz in.

    Host-permission checks (judge/reveal/next question) live in
    GameSessionManager, which has access to Room.host_player_id — the engine
    itself has no notion of "host", only of the contestant ids passed to
    StartGameCommand, mirroring how team/role assignment is Codenames-engine
    state but "who is the host" is room-owned state here.
    """

    def __init__(self, room_code: str) -> None:
        self._room_code = room_code
        self._state_machine = StateMachine(TriviaPhase.LOBBY, TRIVIA_TRANSITIONS)
        self._questions: list[Question] = []
        self._question_index = -1
        self._contestant_ids: list[str] = []
        self._scores: dict[str, int] = {}
        self._buzzed_player_id: str | None = None
        self._locked_out: set[str] = set()

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, BuzzInCommand):
            return self._buzz_in(command)
        if isinstance(command, JudgeAnswerCommand):
            return self._judge_answer(command)
        if isinstance(command, RevealCommand):
            return self._reveal(command)
        if isinstance(command, NextQuestionCommand):
            return self._next_question(command)
        raise ValueError(f"Unsupported command: {command!r}")

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        self._contestant_ids = list(command.active_player_ids)
        self._scores = {player_id: 0 for player_id in self._contestant_ids}
        pool_size = min(len(QUESTION_BANK), _QUESTIONS_PER_GAME)
        self._questions = random.sample(QUESTION_BANK, pool_size)
        self._question_index = 0
        self._buzzed_player_id = None
        self._locked_out = set()
        self._state_machine.transition_to(TriviaPhase.QUESTION_OPEN)
        return [self._question_shown_event()]

    def _question_shown_event(self) -> QuestionShownEvent:
        question = self._questions[self._question_index]
        return QuestionShownEvent(
            question_number=self._question_index + 1,
            total_questions=len(self._questions),
            category=question.category,
            question=question.question,
        )

    def _buzz_in(self, command: BuzzInCommand) -> list[Event]:
        if self._state_machine.phase != TriviaPhase.QUESTION_OPEN:
            raise InvalidGameStateError("Buzzing isn't open right now")
        if command.player_id not in self._contestant_ids:
            raise PermissionDeniedError("Only contestants can buzz in")
        if command.player_id in self._locked_out:
            raise PermissionDeniedError("You've already buzzed in on this question")

        self._buzzed_player_id = command.player_id
        self._state_machine.transition_to(TriviaPhase.ANSWERING)
        return [PlayerBuzzedEvent(player_id=command.player_id)]

    def _judge_answer(self, command: JudgeAnswerCommand) -> list[Event]:
        if self._state_machine.phase != TriviaPhase.ANSWERING:
            raise InvalidGameStateError("No answer is waiting to be judged")

        buzzed_player_id = self._buzzed_player_id
        assert buzzed_player_id is not None

        if command.correct:
            self._scores[buzzed_player_id] = self._scores.get(buzzed_player_id, 0) + _POINTS_PER_CORRECT
            events: list[Event] = [
                AnswerJudgedEvent(player_id=buzzed_player_id, correct=True, score_delta=_POINTS_PER_CORRECT)
            ]
            events.append(self._reveal_current_answer())
            return events

        self._locked_out.add(buzzed_player_id)
        self._buzzed_player_id = None
        events = [AnswerJudgedEvent(player_id=buzzed_player_id, correct=False, score_delta=0)]
        if len(self._locked_out) >= len(self._contestant_ids):
            events.append(self._reveal_current_answer())
        else:
            self._state_machine.transition_to(TriviaPhase.QUESTION_OPEN)
        return events

    def _reveal(self, command: RevealCommand) -> list[Event]:
        if self._state_machine.phase not in (TriviaPhase.QUESTION_OPEN, TriviaPhase.ANSWERING):
            raise InvalidGameStateError("Nothing to reveal right now")
        return [self._reveal_current_answer()]

    def _reveal_current_answer(self) -> AnswerRevealedEvent:
        self._state_machine.transition_to(TriviaPhase.REVEALED)
        self._buzzed_player_id = None
        answer = self._questions[self._question_index].answer
        return AnswerRevealedEvent(answer=answer)

    def _next_question(self, command: NextQuestionCommand) -> list[Event]:
        if self._state_machine.phase != TriviaPhase.REVEALED:
            raise InvalidGameStateError("Reveal the current answer before moving on")

        if self._question_index + 1 >= len(self._questions):
            self._state_machine.transition_to(TriviaPhase.GAME_OVER)
            top_score = max(self._scores.values(), default=0)
            winners = [player_id for player_id, score in self._scores.items() if score == top_score]
            winner_id = winners[0] if len(winners) == 1 else None
            return [GameOverEvent(scores=dict(self._scores), winner_id=winner_id)]

        self._question_index += 1
        self._locked_out = set()
        self._buzzed_player_id = None
        self._state_machine.transition_to(TriviaPhase.QUESTION_OPEN)
        return [self._question_shown_event()]

    def phase_snapshot(self) -> dict[str, object]:
        phase = self._state_machine.phase
        question = self._questions[self._question_index] if 0 <= self._question_index < len(self._questions) else None
        answer_visible = phase in (TriviaPhase.REVEALED, TriviaPhase.GAME_OVER)
        return {
            "phase": phase.value,
            "round_number": self._question_index + 1 if question else 0,
            "total_questions": len(self._questions),
            "category": question.category if question else None,
            "question": question.question if question else None,
            "answer": question.answer if question and answer_visible else None,
            "buzzed_player_id": self._buzzed_player_id,
            "locked_out": sorted(self._locked_out),
            "scores": dict(self._scores),
        }
