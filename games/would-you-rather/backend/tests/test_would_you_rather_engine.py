"""Unit tests for the Would You Rather engine."""
from __future__ import annotations

import asyncio

import pytest

from app.games.would_you_rather.commands import (
    NextQuestionCommand,
    RevealCommand,
    StartGameCommand,
    SubmitVoteCommand,
)
from app.games.would_you_rather.engine import WouldYouRatherEngine
from app.games.would_you_rather.events import (
    GameOverEvent,
    PlayerVotedEvent,
    QuestionShownEvent,
    VotesRevealedEvent,
)
from app.games.would_you_rather.phases import Phase
from app.platform.exceptions import InvalidGameStateError


def make_engine() -> WouldYouRatherEngine:
    return WouldYouRatherEngine("TEST")


def run(coro):
    return asyncio.run(coro)


def start(engine: WouldYouRatherEngine, players: list[str] = None) -> QuestionShownEvent:
    if players is None:
        players = ["p1", "p2", "p3"]
    events = run(engine.handle_command(StartGameCommand(player_id="p1", active_player_ids=players)))
    assert len(events) == 1
    assert isinstance(events[0], QuestionShownEvent)
    return events[0]


class TestStartGame:
    def test_starts_in_question_open(self):
        engine = make_engine()
        event = start(engine)
        assert event.question_number == 1
        assert event.total_questions > 0
        assert event.option_a
        assert event.option_b

    def test_phase_is_question_open(self):
        engine = make_engine()
        start(engine)
        snap = engine.phase_snapshot()
        assert snap["phase"] == Phase.QUESTION_OPEN.value


class TestVoting:
    def test_submit_vote_returns_player_voted_event(self):
        engine = make_engine()
        start(engine)
        events = run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
        assert len(events) == 1
        assert isinstance(events[0], PlayerVotedEvent)
        assert events[0].player_id == "p1"

    def test_vote_overwrites(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
        run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="b")))
        snap = engine.phase_snapshot()
        assert "p1" in snap["voted"]

    def test_voted_list_grows(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
        snap = engine.phase_snapshot()
        assert "p1" in snap["voted"]

    def test_cannot_vote_after_reveal(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
        run(engine.handle_command(RevealCommand(player_id="host")))
        with pytest.raises(InvalidGameStateError):
            run(engine.handle_command(SubmitVoteCommand(player_id="p2", choice="b")))


class TestReveal:
    def test_reveal_returns_votes_revealed_event(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
        run(engine.handle_command(SubmitVoteCommand(player_id="p2", choice="b")))
        events = run(engine.handle_command(RevealCommand(player_id="host")))
        assert len(events) == 1
        assert isinstance(events[0], VotesRevealedEvent)
        assert events[0].votes == {"p1": "a", "p2": "b"}

    def test_reveal_with_no_votes(self):
        engine = make_engine()
        start(engine)
        events = run(engine.handle_command(RevealCommand(player_id="host")))
        assert isinstance(events[0], VotesRevealedEvent)
        assert events[0].votes == {}

    def test_revealed_votes_in_snapshot(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
        run(engine.handle_command(RevealCommand(player_id="host")))
        snap = engine.phase_snapshot()
        assert snap["revealed_votes"] == {"p1": "a"}

    def test_cannot_reveal_twice(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(RevealCommand(player_id="host")))
        with pytest.raises(InvalidGameStateError):
            run(engine.handle_command(RevealCommand(player_id="host")))


class TestNextQuestion:
    def test_next_question_clears_votes(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
        run(engine.handle_command(RevealCommand(player_id="host")))
        run(engine.handle_command(NextQuestionCommand(player_id="host")))
        snap = engine.phase_snapshot()
        assert snap["voted"] == []
        assert snap["revealed_votes"] is None

    def test_next_question_returns_question_shown(self):
        engine = make_engine()
        start(engine)
        run(engine.handle_command(RevealCommand(player_id="host")))
        events = run(engine.handle_command(NextQuestionCommand(player_id="host")))
        assert len(events) == 1
        assert isinstance(events[0], QuestionShownEvent)
        assert events[0].question_number == 2

    def test_cannot_next_question_from_question_open(self):
        engine = make_engine()
        start(engine)
        with pytest.raises(InvalidGameStateError):
            run(engine.handle_command(NextQuestionCommand(player_id="host")))


class TestGameOver:
    def test_game_over_after_last_question(self):
        """Cycle through all questions and confirm GAME_OVER."""
        engine = make_engine()
        q_event = start(engine)
        total = q_event.total_questions
        for i in range(total):
            run(engine.handle_command(RevealCommand(player_id="host")))
            events = run(engine.handle_command(NextQuestionCommand(player_id="host")))
            if i < total - 1:
                assert isinstance(events[0], QuestionShownEvent)
            else:
                assert isinstance(events[0], GameOverEvent)

    def test_game_over_recap_has_all_rounds(self):
        engine = make_engine()
        q_event = start(engine)
        total = q_event.total_questions
        for i in range(total):
            run(engine.handle_command(SubmitVoteCommand(player_id="p1", choice="a")))
            run(engine.handle_command(RevealCommand(player_id="host")))
            events = run(engine.handle_command(NextQuestionCommand(player_id="host")))
        game_over = events[0]
        assert isinstance(game_over, GameOverEvent)
        assert len(game_over.recap) == total
