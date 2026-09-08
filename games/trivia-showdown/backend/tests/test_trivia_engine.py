import asyncio

import pytest

from app.games.trivia_showdown.commands import (
    BuzzInCommand,
    JudgeAnswerCommand,
    NextQuestionCommand,
    RevealCommand,
    StartGameCommand,
)
from app.games.trivia_showdown.engine import TriviaShowdownGameEngine
from app.games.trivia_showdown.events import (
    AnswerJudgedEvent,
    AnswerRevealedEvent,
    GameOverEvent,
    PlayerBuzzedEvent,
    QuestionShownEvent,
)
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError

PLAYER_IDS = [f"p{i}" for i in range(3)]


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def started_engine():
    engine = TriviaShowdownGameEngine("ROOM1")
    events = _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=PLAYER_IDS)))
    return engine, events


def test_start_game_opens_the_first_question(started_engine):
    engine, events = started_engine

    assert len(events) == 1
    assert isinstance(events[0], QuestionShownEvent)
    assert events[0].question_number == 1

    snapshot = engine.phase_snapshot()
    assert snapshot["phase"] == "question_open"
    assert snapshot["round_number"] == 1
    assert snapshot["question"] is not None
    assert snapshot["answer"] is None
    assert snapshot["scores"] == {pid: 0 for pid in PLAYER_IDS}


def test_only_a_contestant_can_buzz_in(started_engine):
    engine, _ = started_engine

    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(BuzzInCommand(player_id="host")))


def test_buzz_in_locks_out_other_buzzes(started_engine):
    engine, _ = started_engine

    result = _run(engine.handle_command(BuzzInCommand(player_id=PLAYER_IDS[0])))

    assert len(result) == 1
    assert isinstance(result[0], PlayerBuzzedEvent)
    assert result[0].player_id == PLAYER_IDS[0]
    assert engine.phase_snapshot()["phase"] == "answering"

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(BuzzInCommand(player_id=PLAYER_IDS[1])))


def test_judge_answer_before_a_buzz_is_rejected(started_engine):
    engine, _ = started_engine

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(JudgeAnswerCommand(player_id="host", correct=True)))


def test_correct_judgment_awards_points_and_reveals(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id=PLAYER_IDS[0])))

    result = _run(engine.handle_command(JudgeAnswerCommand(player_id="host", correct=True)))

    assert isinstance(result[0], AnswerJudgedEvent)
    assert result[0].correct is True
    assert result[0].score_delta == 100
    assert isinstance(result[1], AnswerRevealedEvent)

    snapshot = engine.phase_snapshot()
    assert snapshot["phase"] == "revealed"
    assert snapshot["scores"][PLAYER_IDS[0]] == 100
    assert snapshot["answer"] is not None


def test_wrong_judgment_reopens_buzzing_for_remaining_players(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id=PLAYER_IDS[0])))

    result = _run(engine.handle_command(JudgeAnswerCommand(player_id="host", correct=False)))

    assert len(result) == 1
    assert result[0].correct is False
    assert result[0].score_delta == 0
    snapshot = engine.phase_snapshot()
    assert snapshot["phase"] == "question_open"
    assert snapshot["locked_out"] == [PLAYER_IDS[0]]
    assert snapshot["scores"][PLAYER_IDS[0]] == 0


def test_everyone_locked_out_auto_reveals(started_engine):
    engine, _ = started_engine

    for player_id in PLAYER_IDS[:-1]:
        _run(engine.handle_command(BuzzInCommand(player_id=player_id)))
        _run(engine.handle_command(JudgeAnswerCommand(player_id="host", correct=False)))

    _run(engine.handle_command(BuzzInCommand(player_id=PLAYER_IDS[-1])))
    result = _run(engine.handle_command(JudgeAnswerCommand(player_id="host", correct=False)))

    assert isinstance(result[-1], AnswerRevealedEvent)
    assert engine.phase_snapshot()["phase"] == "revealed"


def test_reveal_can_skip_a_question_no_one_answers(started_engine):
    engine, _ = started_engine

    result = _run(engine.handle_command(RevealCommand(player_id="host")))

    assert isinstance(result[0], AnswerRevealedEvent)
    assert engine.phase_snapshot()["phase"] == "revealed"


def test_next_question_before_reveal_is_rejected(started_engine):
    engine, _ = started_engine

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(NextQuestionCommand(player_id="host")))


def test_next_question_advances_the_round(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(RevealCommand(player_id="host")))

    result = _run(engine.handle_command(NextQuestionCommand(player_id="host")))

    assert isinstance(result[0], QuestionShownEvent)
    assert result[0].question_number == 2
    assert engine.phase_snapshot()["phase"] == "question_open"
    assert engine.phase_snapshot()["locked_out"] == []


def test_next_question_after_final_question_ends_the_game(started_engine):
    engine, _ = started_engine
    total_questions = engine.phase_snapshot()["total_questions"]

    for _ in range(total_questions - 1):
        _run(engine.handle_command(RevealCommand(player_id="host")))
        _run(engine.handle_command(NextQuestionCommand(player_id="host")))

    _run(engine.handle_command(RevealCommand(player_id="host")))
    result = _run(engine.handle_command(NextQuestionCommand(player_id="host")))

    assert isinstance(result[0], GameOverEvent)
    assert engine.phase_snapshot()["phase"] == "game_over"


def test_game_over_reports_a_winner_when_scores_differ(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id=PLAYER_IDS[0])))
    _run(engine.handle_command(JudgeAnswerCommand(player_id="host", correct=True)))
    total_questions = engine.phase_snapshot()["total_questions"]

    for _ in range(total_questions - 1):
        _run(engine.handle_command(NextQuestionCommand(player_id="host")))
        _run(engine.handle_command(RevealCommand(player_id="host")))

    result = _run(engine.handle_command(NextQuestionCommand(player_id="host")))

    game_over = result[0]
    assert isinstance(game_over, GameOverEvent)
    assert game_over.winner_id == PLAYER_IDS[0]
    assert game_over.scores[PLAYER_IDS[0]] == 100
