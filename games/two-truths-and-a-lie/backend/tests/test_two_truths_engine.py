import asyncio

import pytest

from app.games.two_truths_and_a_lie.commands import (
    CastVoteCommand,
    NextRoundCommand,
    RevealCommand,
    StartGameCommand,
    SubmitStatementsCommand,
)
from app.games.two_truths_and_a_lie.engine import TwoTruthsGameEngine
from app.games.two_truths_and_a_lie.events import (
    GameOverEvent,
    PlayerVotedEvent,
    RevealedEvent,
    RoundStartedEvent,
    StatementsSubmittedEvent,
)
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError

PLAYERS = ["p0", "p1", "p2", "p3"]
STATEMENTS = ["I climbed Everest", "I have a twin", "I speak five languages"]
LIE_INDEX = 2  # "I speak five languages" is the lie


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def engine():
    return TwoTruthsGameEngine("ROOM1")


@pytest.fixture
def started_engine(engine):
    events = _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=PLAYERS)))
    return engine, events


@pytest.fixture
def submitted_engine(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(
        SubmitStatementsCommand(player_id=PLAYERS[0], statements=STATEMENTS, lie_index=LIE_INDEX)
    ))
    return engine


# ── Start Game ────────────────────────────────────────────────────────────────

def test_start_game_emits_round_started(started_engine):
    _, events = started_engine
    assert len(events) == 1
    assert isinstance(events[0], RoundStartedEvent)
    assert events[0].storyteller_id == PLAYERS[0]


def test_start_game_enters_submitting_phase(started_engine):
    engine, _ = started_engine
    assert engine.phase_snapshot()["phase"] == "submitting"


def test_start_game_sets_total_rounds_to_player_count(started_engine):
    engine, _ = started_engine
    snap = engine.phase_snapshot()
    assert snap["total_rounds"] == len(PLAYERS)
    assert snap["round_number"] == 1


def test_start_game_initializes_all_scores_to_zero(started_engine):
    engine, _ = started_engine
    assert engine.phase_snapshot()["scores"] == {p: 0 for p in PLAYERS}


# ── Submit Statements ─────────────────────────────────────────────────────────

def test_only_storyteller_can_submit(started_engine):
    engine, _ = started_engine
    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(
            SubmitStatementsCommand(player_id=PLAYERS[1], statements=STATEMENTS, lie_index=LIE_INDEX)
        ))


def test_submit_requires_exactly_3_statements(started_engine):
    engine, _ = started_engine
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(
            SubmitStatementsCommand(player_id=PLAYERS[0], statements=["Only one"], lie_index=0)
        ))


def test_submit_rejects_empty_statement(started_engine):
    engine, _ = started_engine
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(
            SubmitStatementsCommand(player_id=PLAYERS[0], statements=["A", "", "C"], lie_index=0)
        ))


def test_submit_rejects_invalid_lie_index(started_engine):
    engine, _ = started_engine
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(
            SubmitStatementsCommand(player_id=PLAYERS[0], statements=STATEMENTS, lie_index=3)
        ))


def test_submit_advances_to_voting_and_broadcasts_statements(started_engine):
    engine, _ = started_engine
    events = _run(engine.handle_command(
        SubmitStatementsCommand(player_id=PLAYERS[0], statements=STATEMENTS, lie_index=LIE_INDEX)
    ))
    assert len(events) == 1
    assert isinstance(events[0], StatementsSubmittedEvent)
    assert events[0].statements == STATEMENTS
    assert engine.phase_snapshot()["phase"] == "voting"


def test_lie_index_absent_from_snapshot_before_reveal(submitted_engine):
    # Critical security check: lie_index must never appear in phase_snapshot before reveal
    snap = submitted_engine.phase_snapshot()
    assert snap["phase"] == "voting"
    assert snap["lie_index"] is None
    assert snap["correct_voters"] is None


def test_statements_visible_in_snapshot_after_submission(submitted_engine):
    snap = submitted_engine.phase_snapshot()
    assert snap["statements"] == STATEMENTS


# ── Cast Vote ─────────────────────────────────────────────────────────────────

def test_storyteller_cannot_vote(submitted_engine):
    with pytest.raises(PermissionDeniedError):
        _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[0], choice_index=0)))


def test_vote_emits_player_voted(submitted_engine):
    events = _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[1], choice_index=LIE_INDEX)))
    assert any(isinstance(e, PlayerVotedEvent) for e in events)


def test_player_cannot_vote_twice(submitted_engine):
    _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[1], choice_index=0)))
    with pytest.raises(InvalidGameStateError):
        _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[1], choice_index=1)))


def test_voted_count_increments(submitted_engine):
    _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[1], choice_index=0)))
    assert submitted_engine.phase_snapshot()["voted_count"] == 1


def test_last_vote_auto_advances_to_reveal(submitted_engine):
    # 4 players, 1 storyteller → 3 voters
    _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[1], choice_index=LIE_INDEX)))
    _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[2], choice_index=0)))
    events = _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[3], choice_index=LIE_INDEX)))
    assert any(isinstance(e, RevealedEvent) for e in events)
    assert submitted_engine.phase_snapshot()["phase"] == "reveal"


# ── Force Reveal ──────────────────────────────────────────────────────────────

def test_host_can_force_reveal_early(submitted_engine):
    _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[1], choice_index=0)))
    events = _run(submitted_engine.handle_command(RevealCommand(player_id="host")))
    assert any(isinstance(e, RevealedEvent) for e in events)
    assert submitted_engine.phase_snapshot()["phase"] == "reveal"


def test_reveal_outside_voting_is_rejected(started_engine):
    engine, _ = started_engine
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(RevealCommand(player_id="host")))


# ── Scoring ───────────────────────────────────────────────────────────────────

def test_correct_voters_earn_100_points():
    """1 correct out of 3 guessers: correct voter gets 100."""
    engine = TwoTruthsGameEngine("R")
    players = ["p0", "p1", "p2", "p3"]
    _run(engine.handle_command(StartGameCommand(player_id="h", active_player_ids=players)))
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p0", statements=STATEMENTS, lie_index=2)))
    _run(engine.handle_command(CastVoteCommand(player_id="p1", choice_index=2)))   # correct
    _run(engine.handle_command(CastVoteCommand(player_id="p2", choice_index=0)))   # wrong
    _run(engine.handle_command(CastVoteCommand(player_id="p3", choice_index=0)))   # wrong
    snap = engine.phase_snapshot()
    assert snap["scores"]["p1"] == 100
    assert snap["scores"]["p2"] == 0
    assert snap["scores"]["p3"] == 0


def test_storyteller_score_formula_one_correct_out_of_three():
    """1 correct out of 3 guessers → Storyteller gets 100 * 2/3 = 66."""
    engine = TwoTruthsGameEngine("R")
    players = ["p0", "p1", "p2", "p3"]
    _run(engine.handle_command(StartGameCommand(player_id="h", active_player_ids=players)))
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p0", statements=STATEMENTS, lie_index=2)))
    _run(engine.handle_command(CastVoteCommand(player_id="p1", choice_index=2)))   # correct
    _run(engine.handle_command(CastVoteCommand(player_id="p2", choice_index=0)))   # wrong (fooled)
    _run(engine.handle_command(CastVoteCommand(player_id="p3", choice_index=0)))   # wrong (fooled)
    # 2 wrong out of 3 → Storyteller gets int(100 * 2/3) = 66
    snap = engine.phase_snapshot()
    assert snap["scores"]["p0"] == 66


def test_storyteller_score_zero_when_all_guess_correctly():
    """All 3 guessers correct → Storyteller gets 0 (fooled nobody)."""
    engine = TwoTruthsGameEngine("R")
    players = ["p0", "p1", "p2", "p3"]
    _run(engine.handle_command(StartGameCommand(player_id="h", active_player_ids=players)))
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p0", statements=STATEMENTS, lie_index=2)))
    _run(engine.handle_command(CastVoteCommand(player_id="p1", choice_index=2)))
    _run(engine.handle_command(CastVoteCommand(player_id="p2", choice_index=2)))
    _run(engine.handle_command(CastVoteCommand(player_id="p3", choice_index=2)))
    assert engine.phase_snapshot()["scores"]["p0"] == 0


def test_storyteller_score_100_when_all_guessers_wrong():
    """All wrong → Storyteller gets 100 (fooled everyone)."""
    engine = TwoTruthsGameEngine("R")
    players = ["p0", "p1", "p2", "p3"]
    _run(engine.handle_command(StartGameCommand(player_id="h", active_player_ids=players)))
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p0", statements=STATEMENTS, lie_index=2)))
    _run(engine.handle_command(CastVoteCommand(player_id="p1", choice_index=0)))
    _run(engine.handle_command(CastVoteCommand(player_id="p2", choice_index=0)))
    _run(engine.handle_command(CastVoteCommand(player_id="p3", choice_index=0)))
    assert engine.phase_snapshot()["scores"]["p0"] == 100


def test_revealed_event_includes_correct_voters(submitted_engine):
    _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[1], choice_index=LIE_INDEX)))
    _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[2], choice_index=0)))
    events = _run(submitted_engine.handle_command(CastVoteCommand(player_id=PLAYERS[3], choice_index=LIE_INDEX)))
    revealed = next(e for e in events if isinstance(e, RevealedEvent))
    assert revealed.lie_index == LIE_INDEX
    assert set(revealed.correct_voters) == {PLAYERS[1], PLAYERS[3]}


def test_lie_index_visible_in_snapshot_at_reveal(submitted_engine):
    _run(submitted_engine.handle_command(RevealCommand(player_id="host")))
    snap = submitted_engine.phase_snapshot()
    assert snap["phase"] == "reveal"
    assert snap["lie_index"] == LIE_INDEX
    assert snap["correct_voters"] is not None


# ── Round Rotation ────────────────────────────────────────────────────────────

def test_next_round_rotates_storyteller(submitted_engine):
    _run(submitted_engine.handle_command(RevealCommand(player_id="host")))
    events = _run(submitted_engine.handle_command(NextRoundCommand(player_id="host")))
    round_started = next(e for e in events if isinstance(e, RoundStartedEvent))
    assert round_started.storyteller_id == PLAYERS[1]


def test_next_round_before_reveal_is_rejected(submitted_engine):
    with pytest.raises(InvalidGameStateError):
        _run(submitted_engine.handle_command(NextRoundCommand(player_id="host")))


def test_previous_storyteller_can_vote_in_next_round():
    """After rotation, the previous Storyteller is a guesser and can vote."""
    engine = TwoTruthsGameEngine("R")
    players = ["p0", "p1", "p2"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))
    # Round 1: p0 is Storyteller
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p0", statements=STATEMENTS, lie_index=0)))
    _run(engine.handle_command(CastVoteCommand(player_id="p1", choice_index=0)))
    _run(engine.handle_command(CastVoteCommand(player_id="p2", choice_index=0)))
    _run(engine.handle_command(NextRoundCommand(player_id="host")))
    # Round 2: p1 is Storyteller — p0 is now a voter
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p1", statements=STATEMENTS, lie_index=1)))
    # p0 can now vote (no longer Storyteller)
    events = _run(engine.handle_command(CastVoteCommand(player_id="p0", choice_index=1)))
    assert any(isinstance(e, PlayerVotedEvent) for e in events)


def test_new_storyteller_cannot_vote_in_their_own_round():
    """After rotation, the new Storyteller cannot vote in their own round."""
    engine = TwoTruthsGameEngine("R")
    players = ["p0", "p1", "p2"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p0", statements=STATEMENTS, lie_index=0)))
    _run(engine.handle_command(CastVoteCommand(player_id="p1", choice_index=0)))
    _run(engine.handle_command(CastVoteCommand(player_id="p2", choice_index=0)))
    _run(engine.handle_command(NextRoundCommand(player_id="host")))
    _run(engine.handle_command(SubmitStatementsCommand(player_id="p1", statements=STATEMENTS, lie_index=1)))
    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(CastVoteCommand(player_id="p1", choice_index=0)))


# ── Game Over ─────────────────────────────────────────────────────────────────

def test_game_ends_after_all_rounds():
    engine = TwoTruthsGameEngine("R")
    players = ["p0", "p1", "p2"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))
    for i, storyteller in enumerate(players):
        _run(engine.handle_command(SubmitStatementsCommand(player_id=storyteller, statements=STATEMENTS, lie_index=0)))
        voters = [p for p in players if p != storyteller]
        for voter in voters:
            _run(engine.handle_command(CastVoteCommand(player_id=voter, choice_index=0)))
        if i < len(players) - 1:
            events = _run(engine.handle_command(NextRoundCommand(player_id="host")))
            assert any(isinstance(e, RoundStartedEvent) for e in events)
        else:
            events = _run(engine.handle_command(NextRoundCommand(player_id="host")))
            assert any(isinstance(e, GameOverEvent) for e in events)
            assert engine.phase_snapshot()["phase"] == "game_over"
