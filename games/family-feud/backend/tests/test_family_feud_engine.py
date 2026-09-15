import asyncio

import pytest

from app.games.family_feud.commands import (
    BuzzInCommand,
    NextRoundCommand,
    RevealSlotCommand,
    StartGameCommand,
    StealMissCommand,
    StealRevealCommand,
    StrikeCommand,
)
from app.games.family_feud.engine import FamilyFeudGameEngine
from app.games.family_feud.events import (
    GameOverEvent,
    PlayerBuzzedEvent,
    QuestionShownEvent,
    RoundOverEvent,
    SlotRevealedEvent,
    StealPhaseEvent,
    StrikeEvent,
)
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError

TEAM_OF = {"p1": "a", "p2": "a", "p3": "b", "p4": "b"}


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def started_engine():
    engine = FamilyFeudGameEngine("ROOM1")
    events = _run(
        engine.handle_command(StartGameCommand(player_id="host", team_of=TEAM_OF))
    )
    return engine, events


def test_start_game_opens_first_question(started_engine):
    engine, events = started_engine

    assert len(events) == 1
    assert isinstance(events[0], QuestionShownEvent)
    assert events[0].round_number == 1

    snap = engine.phase_snapshot()
    assert snap["phase"] == "question_open"
    assert snap["round_number"] == 1
    assert snap["team_scores"] == {"a": 0, "b": 0}
    assert snap["team_of"] == TEAM_OF
    assert snap["controlling_team"] is None
    assert snap["strikes"] == 0
    # All board slots hidden
    for slot in snap["board"]:
        assert slot["revealed"] is False
        assert slot["text"] is None


def test_only_team_member_can_buzz_in(started_engine):
    engine, _ = started_engine

    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(BuzzInCommand(player_id="host")))


def test_buzz_in_sets_controlling_team(started_engine):
    engine, _ = started_engine

    events = _run(engine.handle_command(BuzzInCommand(player_id="p1")))

    assert len(events) == 1
    assert isinstance(events[0], PlayerBuzzedEvent)
    assert events[0].player_id == "p1"
    assert events[0].team == "a"

    snap = engine.phase_snapshot()
    assert snap["phase"] == "answering"
    assert snap["controlling_team"] == "a"
    assert snap["strikes"] == 0


def test_buzz_requires_question_open_phase(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(BuzzInCommand(player_id="p3")))


def test_reveal_slot_shows_answer(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))

    events = _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=0)))

    assert len(events) == 1
    assert isinstance(events[0], SlotRevealedEvent)
    assert events[0].slot_index == 0
    assert events[0].text is not None
    assert events[0].points > 0

    snap = engine.phase_snapshot()
    assert snap["board"][0]["revealed"] is True
    assert snap["board"][0]["text"] is not None
    assert snap["phase"] == "answering"


def test_reveal_already_revealed_slot_raises(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))
    _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=0)))

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=0)))


def test_reveal_all_slots_ends_round_with_controlling_team(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))

    board_size = len(engine.phase_snapshot()["board"])
    for i in range(board_size - 1):
        _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=i)))

    events = _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=board_size - 1)))

    round_over = next(e for e in events if isinstance(e, RoundOverEvent))
    assert round_over.team_awarded == "a"
    assert round_over.points > 0

    snap = engine.phase_snapshot()
    assert snap["phase"] == "round_over"
    assert snap["team_scores"]["a"] == round_over.points


def test_three_strikes_trigger_steal_phase(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))

    for _ in range(2):
        events = _run(engine.handle_command(StrikeCommand(player_id="host")))
        assert isinstance(events[0], StrikeEvent)
        assert engine.phase_snapshot()["phase"] == "answering"

    events = _run(engine.handle_command(StrikeCommand(player_id="host")))

    assert isinstance(events[0], StrikeEvent)
    assert events[0].strikes == 3
    steal_event = next(e for e in events if isinstance(e, StealPhaseEvent))
    assert steal_event.stealing_team == "b"

    snap = engine.phase_snapshot()
    assert snap["phase"] == "steal"


def test_steal_success_awards_points_to_stealing_team(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))
    _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=0)))
    for _ in range(3):
        _run(engine.handle_command(StrikeCommand(player_id="host")))

    events = _run(engine.handle_command(StealRevealCommand(player_id="host", slot_index=1)))

    round_over = next(e for e in events if isinstance(e, RoundOverEvent))
    assert round_over.team_awarded == "b"
    assert round_over.points > 0

    snap = engine.phase_snapshot()
    assert snap["team_scores"]["b"] == round_over.points
    assert snap["team_scores"]["a"] == 0
    assert snap["phase"] == "round_over"


def test_steal_miss_awards_points_to_controlling_team(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))
    _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=0)))
    for _ in range(3):
        _run(engine.handle_command(StrikeCommand(player_id="host")))

    events = _run(engine.handle_command(StealMissCommand(player_id="host")))

    round_over = next(e for e in events if isinstance(e, RoundOverEvent))
    assert round_over.team_awarded == "a"
    assert round_over.points > 0

    snap = engine.phase_snapshot()
    assert snap["team_scores"]["a"] == round_over.points
    assert snap["team_scores"]["b"] == 0
    assert snap["phase"] == "round_over"


def test_next_round_advances_board(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(BuzzInCommand(player_id="p1")))
    for _ in range(3):
        _run(engine.handle_command(StrikeCommand(player_id="host")))
    _run(engine.handle_command(StealMissCommand(player_id="host")))

    events = _run(engine.handle_command(NextRoundCommand(player_id="host")))

    assert isinstance(events[0], QuestionShownEvent)
    assert events[0].round_number == 2

    snap = engine.phase_snapshot()
    assert snap["phase"] == "question_open"
    assert snap["strikes"] == 0
    assert snap["controlling_team"] is None
    for slot in snap["board"]:
        assert slot["revealed"] is False


def test_next_round_before_round_over_is_rejected(started_engine):
    engine, _ = started_engine

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(NextRoundCommand(player_id="host")))


def test_game_over_after_final_round(started_engine):
    engine, _ = started_engine
    total_rounds = engine.phase_snapshot()["total_rounds"]

    for _ in range(total_rounds - 1):
        _run(engine.handle_command(BuzzInCommand(player_id="p1")))
        for _ in range(3):
            _run(engine.handle_command(StrikeCommand(player_id="host")))
        _run(engine.handle_command(StealMissCommand(player_id="host")))
        _run(engine.handle_command(NextRoundCommand(player_id="host")))

    _run(engine.handle_command(BuzzInCommand(player_id="p1")))
    for _ in range(3):
        _run(engine.handle_command(StrikeCommand(player_id="host")))
    _run(engine.handle_command(StealMissCommand(player_id="host")))
    events = _run(engine.handle_command(NextRoundCommand(player_id="host")))

    assert isinstance(events[0], GameOverEvent)
    assert engine.phase_snapshot()["phase"] == "game_over"


def test_game_over_tie_has_no_winning_team():
    engine = FamilyFeudGameEngine("ROOM2")
    _run(engine.handle_command(StartGameCommand(player_id="host", team_of={"p1": "a", "p2": "b"})))
    total_rounds = engine.phase_snapshot()["total_rounds"]

    for _ in range(total_rounds - 1):
        _run(engine.handle_command(BuzzInCommand(player_id="p1")))
        for _ in range(3):
            _run(engine.handle_command(StrikeCommand(player_id="host")))
        _run(engine.handle_command(StealMissCommand(player_id="host")))
        _run(engine.handle_command(NextRoundCommand(player_id="host")))

    _run(engine.handle_command(BuzzInCommand(player_id="p1")))
    for _ in range(3):
        _run(engine.handle_command(StrikeCommand(player_id="host")))
    _run(engine.handle_command(StealMissCommand(player_id="host")))
    events = _run(engine.handle_command(NextRoundCommand(player_id="host")))

    game_over = events[0]
    assert isinstance(game_over, GameOverEvent)
    assert game_over.winning_team is None


def test_game_over_reports_winning_team_when_scores_differ(started_engine):
    engine, _ = started_engine
    total_rounds = engine.phase_snapshot()["total_rounds"]

    _run(engine.handle_command(BuzzInCommand(player_id="p1")))
    board_size = len(engine.phase_snapshot()["board"])
    for i in range(board_size):
        _run(engine.handle_command(RevealSlotCommand(player_id="host", slot_index=i)))

    for _ in range(total_rounds - 1):
        _run(engine.handle_command(NextRoundCommand(player_id="host")))
        _run(engine.handle_command(BuzzInCommand(player_id="p1")))
        for _ in range(3):
            _run(engine.handle_command(StrikeCommand(player_id="host")))
        _run(engine.handle_command(StealMissCommand(player_id="host")))

    events = _run(engine.handle_command(NextRoundCommand(player_id="host")))

    game_over = events[0]
    assert isinstance(game_over, GameOverEvent)
    assert game_over.winning_team == "a"
    assert game_over.team_scores["a"] > game_over.team_scores["b"]


def test_team_assignment_validation_no_team_a():
    engine = FamilyFeudGameEngine("ROOM3")
    _run(engine.handle_command(StartGameCommand(player_id="host", team_of={"p1": "b", "p2": "b"})))
    snap = engine.phase_snapshot()
    assert snap["team_of"] == {"p1": "b", "p2": "b"}


def test_phase_snapshot_lobby_defaults():
    engine = FamilyFeudGameEngine("ROOM4")
    snap = engine.phase_snapshot()
    assert snap["phase"] == "lobby"
    assert snap["board"] == []
    assert snap["team_of"] == {}
    assert snap["team_scores"] == {"a": 0, "b": 0}
