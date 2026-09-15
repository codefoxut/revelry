import asyncio

import pytest

from app.games.wavelength.commands import (
    GiveClueCommand,
    NextRoundCommand,
    RevealCommand,
    StartGameCommand,
    SubmitGuessCommand,
)
from app.games.wavelength.engine import WavelengthEngine, _score_for_distance
from app.games.wavelength.events import (
    ClueGivenEvent,
    GameOverEvent,
    PlayerGuessedEvent,
    RevealedEvent,
    RoundStartedEvent,
)
from app.games.wavelength.phases import Phase
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError

PLAYER_IDS = ["p0", "p1", "p2"]  # 3 players: 1 psychic + 2 guessers


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def started_engine():
    engine = WavelengthEngine("ROOM1")
    events = _run(engine.handle_command(StartGameCommand(player_id="p0", active_player_ids=PLAYER_IDS, total_rounds=3)))
    return engine, events


def _psychic_id(engine: WavelengthEngine) -> str:
    return engine._current_psychic_id  # type: ignore[return-value]


def _guesser_ids(engine: WavelengthEngine) -> list[str]:
    return [pid for pid in engine._player_order if pid != _psychic_id(engine)]


# ---- Scoring bands ----

def test_score_for_distance_bands():
    assert _score_for_distance(0) == 4
    assert _score_for_distance(2) == 4
    assert _score_for_distance(2.1) == 3
    assert _score_for_distance(6) == 3
    assert _score_for_distance(6.1) == 2
    assert _score_for_distance(12) == 2
    assert _score_for_distance(12.1) == 1
    assert _score_for_distance(20) == 1
    assert _score_for_distance(20.1) == 0


# ---- start_game ----

def test_start_game_emits_round_started_event(started_engine):
    engine, events = started_engine
    assert len(events) == 1
    assert isinstance(events[0], RoundStartedEvent)
    assert events[0].psychic_id in PLAYER_IDS
    assert events[0].round_number == 1
    assert events[0].left_label != ""
    assert events[0].right_label != ""


def test_start_game_sets_phase_to_clue_giving(started_engine):
    engine, _ = started_engine
    assert engine._state_machine.phase == Phase.CLUE_GIVING


def test_start_game_initialises_scores_for_all_players(started_engine):
    engine, _ = started_engine
    assert set(engine._scores.keys()) == set(PLAYER_IDS)
    assert all(v == 0 for v in engine._scores.values())


# ---- target privacy (THE most important test) ----

def test_target_position_never_in_phase_snapshot(started_engine):
    engine, _ = started_engine
    snapshot = engine.phase_snapshot()
    # target_position key must be None for everyone (not the actual value)
    assert snapshot["target_position"] is None


def test_get_target_position_returns_none_for_non_psychic(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    for pid in PLAYER_IDS:
        if pid != psychic:
            assert engine.get_target_position(pid) is None


def test_get_target_position_returns_value_for_psychic_during_clue_giving(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    target = engine.get_target_position(psychic)
    assert target is not None
    assert 0.0 <= target <= 100.0


def test_get_target_position_returns_none_during_lobby():
    engine = WavelengthEngine("ROOM1")
    assert engine.get_target_position("p0") is None


def test_get_target_position_returns_none_during_reveal(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    for gid in guessers:
        _run(engine.handle_command(SubmitGuessCommand(player_id=gid, position=50.0)))
    assert engine._state_machine.phase == Phase.REVEAL
    # target is now public (in phase_snapshot), so get_target_position returns None
    assert engine.get_target_position(psychic) is None


# ---- give_clue ----

def test_only_psychic_can_give_clue(started_engine):
    engine, _ = started_engine
    guesser = _guesser_ids(engine)[0]
    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(GiveClueCommand(player_id=guesser, clue_text="warm")))


def test_give_clue_advances_to_guessing(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    assert engine._state_machine.phase == Phase.GUESSING


def test_give_clue_emits_clue_given_event(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    events = _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    assert len(events) == 1
    assert isinstance(events[0], ClueGivenEvent)
    assert events[0].clue_text == "warm"


def test_give_clue_without_clue_text_is_allowed(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    events = _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="")))
    assert engine._state_machine.phase == Phase.GUESSING
    assert isinstance(events[0], ClueGivenEvent)


# ---- submit_guess ----

def test_psychic_cannot_submit_guess(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(SubmitGuessCommand(player_id=psychic, position=50.0)))


def test_guess_before_clue_is_rejected(started_engine):
    engine, _ = started_engine
    guesser = _guesser_ids(engine)[0]
    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(SubmitGuessCommand(player_id=guesser, position=50.0)))


def test_guess_emits_player_guessed_event(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))

    events = _run(engine.handle_command(SubmitGuessCommand(player_id=guessers[0], position=60.0)))
    assert isinstance(events[0], PlayerGuessedEvent)
    assert events[0].player_id == guessers[0]
    assert events[0].guessed_count == 1


def test_all_guessers_submitting_auto_advances_to_reveal(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    for i, gid in enumerate(guessers):
        _run(engine.handle_command(SubmitGuessCommand(player_id=gid, position=50.0 + i)))
    assert engine._state_machine.phase == Phase.REVEAL


def test_auto_reveal_emits_revealed_event(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    all_events: list = []
    for i, gid in enumerate(guessers):
        all_events.extend(_run(engine.handle_command(SubmitGuessCommand(player_id=gid, position=50.0))))
    revealed = next(e for e in all_events if isinstance(e, RevealedEvent))
    assert 0.0 <= revealed.target_position <= 100.0
    assert set(revealed.guesses.keys()) == set(guessers)


# ---- force reveal ----

def test_only_psychic_can_force_reveal(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(RevealCommand(player_id=guessers[0])))


def test_force_reveal_advances_to_reveal(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    _run(engine.handle_command(RevealCommand(player_id=psychic)))
    assert engine._state_machine.phase == Phase.REVEAL


# ---- scoring ----

def test_scoring_awards_correct_points(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    # Force a known target so we can predict scores
    engine._target_position = 50.0
    _run(engine.handle_command(SubmitGuessCommand(player_id=guessers[0], position=51.0)))  # distance 1 → 4 pts
    _run(engine.handle_command(SubmitGuessCommand(player_id=guessers[1], position=60.0)))  # distance 10 → 2 pts

    assert engine._scores[guessers[0]] == 4
    assert engine._scores[guessers[1]] == 2
    # Psychic gets max guesser score = 4
    assert engine._scores[psychic] == 4


# ---- rotation ----

def test_psychic_rotates_to_next_player_after_next_round(started_engine):
    engine, start_events = started_engine
    first_psychic_idx = engine._psychic_index
    first_psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)

    _run(engine.handle_command(GiveClueCommand(player_id=first_psychic, clue_text="warm")))
    for gid in guessers:
        _run(engine.handle_command(SubmitGuessCommand(player_id=gid, position=50.0)))
    # Force next_round using any player (engine doesn't validate who calls next_round)
    _run(engine.handle_command(NextRoundCommand(player_id="p0")))

    assert engine._psychic_index == first_psychic_idx + 1
    assert _psychic_id(engine) != first_psychic


def test_psychic_rotation_wraps_around(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)

    for _ in range(len(PLAYER_IDS)):
        current_psychic = _psychic_id(engine)
        current_guessers = [pid for pid in engine._player_order if pid != current_psychic]
        _run(engine.handle_command(GiveClueCommand(player_id=current_psychic, clue_text="x")))
        for gid in current_guessers:
            _run(engine.handle_command(SubmitGuessCommand(player_id=gid, position=50.0)))
        _run(engine.handle_command(NextRoundCommand(player_id="p0")))

    # After len(PLAYER_IDS) rounds, back to the original psychic
    assert _psychic_id(engine) == psychic


# ---- game over ----

def test_game_over_after_all_rounds(started_engine):
    engine, _ = started_engine
    for _ in range(engine._total_rounds):
        current_psychic = _psychic_id(engine)
        current_guessers = [pid for pid in engine._player_order if pid != current_psychic]
        _run(engine.handle_command(GiveClueCommand(player_id=current_psychic, clue_text="x")))
        for gid in current_guessers:
            _run(engine.handle_command(SubmitGuessCommand(player_id=gid, position=50.0)))
        events = _run(engine.handle_command(NextRoundCommand(player_id="p0")))

    assert engine._state_machine.phase == Phase.GAME_OVER
    game_over_events = [e for e in events if isinstance(e, GameOverEvent)]
    assert len(game_over_events) == 1
    assert set(game_over_events[0].scores.keys()) == set(PLAYER_IDS)


# ---- phase_snapshot ----

def test_phase_snapshot_has_correct_shape_during_clue_giving(started_engine):
    engine, _ = started_engine
    snapshot = engine.phase_snapshot()
    assert snapshot["phase"] == "clue_giving"
    assert snapshot["target_position"] is None  # secret
    assert snapshot["guesses"] is None
    assert snapshot["points_awarded"] is None
    assert snapshot["guessed_count"] == 0
    assert snapshot["total_rounds"] == 3


def test_phase_snapshot_reveals_target_and_guesses_at_reveal(started_engine):
    engine, _ = started_engine
    psychic = _psychic_id(engine)
    guessers = _guesser_ids(engine)
    _run(engine.handle_command(GiveClueCommand(player_id=psychic, clue_text="warm")))
    engine._target_position = 50.0
    for gid in guessers:
        _run(engine.handle_command(SubmitGuessCommand(player_id=gid, position=50.0)))

    snapshot = engine.phase_snapshot()
    assert snapshot["phase"] == "reveal"
    assert snapshot["target_position"] == 50.0  # public at reveal
    assert snapshot["guesses"] is not None
    assert snapshot["points_awarded"] is not None
