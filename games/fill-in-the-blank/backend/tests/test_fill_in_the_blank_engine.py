import asyncio

import pytest

from app.games.fill_in_the_blank.commands import (
    CastVoteCommand,
    NextPromptCommand,
    RevealCommand,
    StartGameCommand,
    StartVoteCommand,
    SubmitAnswerCommand,
)
from app.games.fill_in_the_blank.engine import FillInTheBlankGameEngine
from app.games.fill_in_the_blank.events import (
    GameOverEvent,
    PlayerSubmittedEvent,
    PlayerVotedEvent,
    PromptShownEvent,
    RoundOverEvent,
    SubmissionsRevealedEvent,
    VoteResultsEvent,
)
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError

PLAYERS = ["p0", "p1", "p2", "p3"]


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def engine():
    return FillInTheBlankGameEngine("ROOM1")


@pytest.fixture
def started_engine(engine):
    events = _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=PLAYERS)))
    return engine, events


@pytest.fixture
def submitted_engine(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="a chainsaw")))
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p1", text="a live parrot")))
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p2", text="my confidence")))
    return engine


@pytest.fixture
def revealed_engine(submitted_engine):
    _run(submitted_engine.handle_command(RevealCommand(player_id="host")))
    return submitted_engine


@pytest.fixture
def voting_engine(revealed_engine):
    _run(revealed_engine.handle_command(StartVoteCommand(player_id="host")))
    return revealed_engine


# ── Start Game ────────────────────────────────────────────────────────────────

def test_start_game_emits_prompt_shown(started_engine):
    _, events = started_engine
    assert len(events) == 1
    assert isinstance(events[0], PromptShownEvent)
    assert events[0].question_number == 1
    assert events[0].total_questions == 7
    assert events[0].prompt  # non-empty


def test_start_game_enters_prompt_open_phase(started_engine):
    engine, _ = started_engine
    assert engine.phase_snapshot()["phase"] == "prompt_open"


def test_start_game_initializes_scores_to_zero(started_engine):
    engine, _ = started_engine
    assert engine.phase_snapshot()["scores"] == {p: 0 for p in PLAYERS}


# ── Submit Answer ─────────────────────────────────────────────────────────────

def test_submit_answer_emits_player_submitted(started_engine):
    engine, _ = started_engine
    events = _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="a chainsaw")))
    assert len(events) == 1
    assert isinstance(events[0], PlayerSubmittedEvent)
    assert events[0].player_id == "p0"


def test_submitted_count_increments(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="a chainsaw")))
    assert engine.phase_snapshot()["submitted_count"] == 1


def test_player_cannot_submit_twice(started_engine):
    engine, _ = started_engine
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="a chainsaw")))
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="something else")))


def test_submit_rejects_empty_text(started_engine):
    engine, _ = started_engine
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="   ")))


def test_unknown_player_cannot_submit(started_engine):
    engine, _ = started_engine
    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(SubmitAnswerCommand(player_id="outsider", text="hello")))


# ── Reveal ────────────────────────────────────────────────────────────────────

def test_reveal_emits_submissions_revealed(submitted_engine):
    events = _run(submitted_engine.handle_command(RevealCommand(player_id="host")))
    assert len(events) == 1
    assert isinstance(events[0], SubmissionsRevealedEvent)


def test_submissions_revealed_has_no_author_id(submitted_engine):
    events = _run(submitted_engine.handle_command(RevealCommand(player_id="host")))
    revealed = events[0]
    assert isinstance(revealed, SubmissionsRevealedEvent)
    for sub in revealed.submissions:
        assert "author_id" not in sub, "author_id must not appear in SubmissionsRevealedEvent"


def test_submissions_in_snapshot_have_no_author_id(submitted_engine):
    _run(submitted_engine.handle_command(RevealCommand(player_id="host")))
    snap = submitted_engine.phase_snapshot()
    assert snap["phase"] == "submissions_revealed"
    for sub in snap["submissions"]:
        assert "author_id" not in sub, "author_id must not appear in phase_snapshot before results"


def test_reveal_outside_prompt_open_is_rejected(started_engine):
    engine, _ = started_engine
    # In prompt_open with no submissions — reveal should still work (0 submissions allowed)
    # Try reveal during LOBBY (before start) — but engine is already started in fixture
    # Instead test reveal during voting
    _run(engine.handle_command(RevealCommand(player_id="host")))  # valid: prompt_open -> submissions_revealed
    _run(engine.handle_command(StartVoteCommand(player_id="host")))
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(RevealCommand(player_id="host")))


# ── Start Vote ────────────────────────────────────────────────────────────────

def test_start_vote_transitions_to_voting(revealed_engine):
    _run(revealed_engine.handle_command(StartVoteCommand(player_id="host")))
    assert revealed_engine.phase_snapshot()["phase"] == "voting"


def test_start_vote_outside_submissions_revealed_is_rejected(started_engine):
    engine, _ = started_engine
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(StartVoteCommand(player_id="host")))


# ── Cast Vote — self-vote rejection (critical) ────────────────────────────────

def test_self_vote_is_rejected(voting_engine):
    snap = voting_engine.phase_snapshot()
    submissions = snap["submissions"]
    # p0 submitted "a chainsaw" — find that submission by text and try to vote for it.
    p0_sid = next(s["submission_id"] for s in submissions if s["text"] == "a chainsaw")
    with pytest.raises(PermissionDeniedError):
        _run(voting_engine.handle_command(CastVoteCommand(player_id="p0", submission_id=p0_sid)))


def test_cast_vote_emits_player_voted(voting_engine):
    snap = voting_engine.phase_snapshot()
    submissions = snap["submissions"]
    # p3 didn't submit, so they can vote for any submission
    sid = submissions[0]["submission_id"]
    events = _run(voting_engine.handle_command(CastVoteCommand(player_id="p3", submission_id=sid)))
    assert any(isinstance(e, PlayerVotedEvent) for e in events)


def test_player_cannot_vote_twice(voting_engine):
    snap = voting_engine.phase_snapshot()
    sid = snap["submissions"][0]["submission_id"]
    try:
        _run(voting_engine.handle_command(CastVoteCommand(player_id="p3", submission_id=sid)))
    except PermissionDeniedError:
        sid = snap["submissions"][1]["submission_id"]
        _run(voting_engine.handle_command(CastVoteCommand(player_id="p3", submission_id=sid)))
    with pytest.raises(InvalidGameStateError):
        _run(voting_engine.handle_command(CastVoteCommand(player_id="p3", submission_id=sid)))


def test_voted_count_increments(voting_engine):
    snap = voting_engine.phase_snapshot()
    sid = snap["submissions"][0]["submission_id"]
    try:
        _run(voting_engine.handle_command(CastVoteCommand(player_id="p3", submission_id=sid)))
    except PermissionDeniedError:
        sid = snap["submissions"][1]["submission_id"]
        _run(voting_engine.handle_command(CastVoteCommand(player_id="p3", submission_id=sid)))
    assert voting_engine.phase_snapshot()["voted_count"] == 1


def test_unknown_submission_id_is_rejected(voting_engine):
    with pytest.raises(InvalidGameStateError):
        _run(voting_engine.handle_command(CastVoteCommand(player_id="p3", submission_id="nonexistent-id")))


# ── NextPrompt from voting → results ─────────────────────────────────────────

def test_next_prompt_from_voting_computes_results(voting_engine):
    events = _run(voting_engine.handle_command(NextPromptCommand(player_id="host")))
    assert any(isinstance(e, VoteResultsEvent) for e in events)
    assert any(isinstance(e, RoundOverEvent) for e in events)
    assert voting_engine.phase_snapshot()["phase"] == "results"


def test_vote_results_contain_author_id(voting_engine):
    events = _run(voting_engine.handle_command(NextPromptCommand(player_id="host")))
    vote_results = next(e for e in events if isinstance(e, VoteResultsEvent))
    for entry in vote_results.results:
        assert "author_id" in entry, "author_id must appear in VoteResultsEvent"
        assert "votes" in entry
        assert "text" in entry
        assert "submission_id" in entry


def test_results_in_snapshot_contain_author_id(voting_engine):
    _run(voting_engine.handle_command(NextPromptCommand(player_id="host")))
    snap = voting_engine.phase_snapshot()
    assert snap["results"] is not None
    for entry in snap["results"]:
        assert "author_id" in entry


# ── Scoring ───────────────────────────────────────────────────────────────────

def test_points_per_vote_received():
    """Each vote received = 100 points for the author."""
    engine = FillInTheBlankGameEngine("R")
    players = ["p0", "p1", "p2", "p3"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="A")))
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p1", text="B")))
    _run(engine.handle_command(RevealCommand(player_id="host")))
    _run(engine.handle_command(StartVoteCommand(player_id="host")))

    snap = engine.phase_snapshot()
    # p2 and p3 vote; find p0's submission_id
    p0_sid = next(
        s["submission_id"]
        for s in snap["submissions"]
        if s["text"] == "A"
    )
    p1_sid = next(
        s["submission_id"]
        for s in snap["submissions"]
        if s["text"] == "B"
    )

    # p2 votes for p0, p3 votes for p0
    _run(engine.handle_command(CastVoteCommand(player_id="p2", submission_id=p0_sid)))
    _run(engine.handle_command(CastVoteCommand(player_id="p3", submission_id=p0_sid)))
    _run(engine.handle_command(NextPromptCommand(player_id="host")))

    snap = engine.phase_snapshot()
    assert snap["scores"]["p0"] == 200  # 2 votes × 100
    assert snap["scores"]["p1"] == 0
    _ = p1_sid  # referenced to avoid lint warning


def test_tie_scoring_all_authors_score_full():
    """If two submissions each get 2 votes, both authors score 200."""
    engine = FillInTheBlankGameEngine("R")
    players = ["p0", "p1", "p2", "p3"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="A")))
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p1", text="B")))
    _run(engine.handle_command(RevealCommand(player_id="host")))
    _run(engine.handle_command(StartVoteCommand(player_id="host")))

    snap = engine.phase_snapshot()
    p0_sid = next(s["submission_id"] for s in snap["submissions"] if s["text"] == "A")
    p1_sid = next(s["submission_id"] for s in snap["submissions"] if s["text"] == "B")

    # p2 and p3 split their votes
    _run(engine.handle_command(CastVoteCommand(player_id="p2", submission_id=p0_sid)))
    _run(engine.handle_command(CastVoteCommand(player_id="p3", submission_id=p1_sid)))
    _run(engine.handle_command(NextPromptCommand(player_id="host")))

    snap = engine.phase_snapshot()
    assert snap["scores"]["p0"] == 100
    assert snap["scores"]["p1"] == 100


def test_no_submissions_round_proceeds_cleanly():
    """If nobody submits (AFK all), next_prompt from voting should still work."""
    engine = FillInTheBlankGameEngine("R")
    players = ["p0", "p1", "p2"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))
    # No one submits
    _run(engine.handle_command(RevealCommand(player_id="host")))
    _run(engine.handle_command(StartVoteCommand(player_id="host")))
    events = _run(engine.handle_command(NextPromptCommand(player_id="host")))
    assert any(isinstance(e, VoteResultsEvent) for e in events)
    assert engine.phase_snapshot()["phase"] == "results"


def test_one_submission_round_proceeds_cleanly():
    """If only one person submits, they can't self-vote — voted_count stays 0."""
    engine = FillInTheBlankGameEngine("R")
    players = ["p0", "p1", "p2"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))
    _run(engine.handle_command(SubmitAnswerCommand(player_id="p0", text="A")))
    _run(engine.handle_command(RevealCommand(player_id="host")))
    _run(engine.handle_command(StartVoteCommand(player_id="host")))

    snap = engine.phase_snapshot()
    only_sid = snap["submissions"][0]["submission_id"]
    # p0 tries to vote for their own submission — server must reject
    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(CastVoteCommand(player_id="p0", submission_id=only_sid)))

    # Nobody else voted; host advances
    events = _run(engine.handle_command(NextPromptCommand(player_id="host")))
    assert any(isinstance(e, VoteResultsEvent) for e in events)


# ── NextPrompt from results → next question or game over ─────────────────────

def test_next_prompt_from_results_advances_question_number(voting_engine):
    _run(voting_engine.handle_command(NextPromptCommand(player_id="host")))  # voting -> results
    events = _run(voting_engine.handle_command(NextPromptCommand(player_id="host")))  # results -> prompt_open
    assert any(isinstance(e, PromptShownEvent) for e in events)
    prompt_event = next(e for e in events if isinstance(e, PromptShownEvent))
    assert prompt_event.question_number == 2


def test_next_prompt_from_results_resets_submissions(voting_engine):
    _run(voting_engine.handle_command(NextPromptCommand(player_id="host")))
    _run(voting_engine.handle_command(NextPromptCommand(player_id="host")))
    snap = voting_engine.phase_snapshot()
    assert snap["submitted_count"] == 0
    assert snap["submissions"] is None


def test_game_ends_after_all_questions():
    engine = FillInTheBlankGameEngine("R")
    players = ["p0", "p1", "p2"]
    _run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))

    total = engine.phase_snapshot()["total_questions"]
    for q in range(total):
        assert engine.phase_snapshot()["phase"] == "prompt_open"
        _run(engine.handle_command(RevealCommand(player_id="host")))
        _run(engine.handle_command(StartVoteCommand(player_id="host")))
        _run(engine.handle_command(NextPromptCommand(player_id="host")))  # -> results
        if q < total - 1:
            events = _run(engine.handle_command(NextPromptCommand(player_id="host")))  # -> next prompt
            assert any(isinstance(e, PromptShownEvent) for e in events)
        else:
            events = _run(engine.handle_command(NextPromptCommand(player_id="host")))  # -> game over
            assert any(isinstance(e, GameOverEvent) for e in events)
            assert engine.phase_snapshot()["phase"] == "game_over"


def test_next_prompt_outside_valid_phase_is_rejected(started_engine):
    engine, _ = started_engine
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(NextPromptCommand(player_id="host")))
