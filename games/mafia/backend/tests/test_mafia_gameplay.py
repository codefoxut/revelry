import asyncio

import pytest

from app.games.mafia.commands import AdvancePhaseCommand, CastVoteCommand, StartGameCommand, SubmitNightActionCommand
from app.games.mafia.engine import MafiaGameEngine
from app.games.mafia.events import (
    EliminationResultEvent,
    GameOverEvent,
    InvestigationResultEvent,
    NightResultEvent,
)
from app.games.mafia.phases import MafiaPhase
from app.games.mafia.roles import ROLE_REGISTRY
from app.platform.exceptions import InvalidGameStateError

_PLAYERS = ["p1", "p2", "p3", "p4"]


def _start(engine, players=_PLAYERS):
    asyncio.run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=players)))


def _force_roles(engine, mapping):
    """Pin each player's role for a deterministic test scenario, bypassing
    the random assignment step11 doesn't need to re-test here.
    """
    engine._roles = {player_id: ROLE_REGISTRY[role_key] for player_id, role_key in mapping.items()}


def _advance(engine):
    return asyncio.run(engine.handle_command(AdvancePhaseCommand(player_id="host")))


def _night_action(engine, player_id, target_id):
    return asyncio.run(
        engine.handle_command(SubmitNightActionCommand(player_id=player_id, target_player_id=target_id))
    )


def _vote(engine, player_id, target_id):
    return asyncio.run(engine.handle_command(CastVoteCommand(player_id=player_id, target_player_id=target_id)))


def _standard_engine():
    engine = MafiaGameEngine("ABCDE")
    _start(engine)
    _force_roles(engine, {"p1": "mafia", "p2": "doctor", "p3": "detective", "p4": "villager"})
    return engine


def test_mafia_kill_eliminates_target_when_unprotected():
    engine = _standard_engine()
    _night_action(engine, "p1", "p4")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id == "p4"
    assert engine.is_alive("p4") is False
    assert engine.phase == MafiaPhase.DAY


def test_doctor_protection_cancels_mafia_kill():
    engine = _standard_engine()
    _night_action(engine, "p1", "p4")
    _night_action(engine, "p2", "p4")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id is None
    assert engine.is_alive("p4") is True


def test_detective_investigation_resolves_immediately():
    engine = _standard_engine()

    events = _night_action(engine, "p3", "p1")

    assert events == [InvestigationResultEvent(player_id="p3", target_player_id="p1", team="mafia")]


def test_night_action_rejected_outside_night_phase():
    engine = _standard_engine()
    _advance(engine)  # -> DAY

    with pytest.raises(InvalidGameStateError):
        _night_action(engine, "p1", "p4")


def test_night_action_rejected_for_dead_player():
    # 5 players so a villager can die on both night 1 and day 1 without the
    # remaining mafia/town ratio already deciding the game (which would
    # short-circuit before a round 2 exists to test against).
    engine = MafiaGameEngine("R2TST")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "detective", "p3": "doctor", "p4": "villager", "p5": "villager"},
    )

    _night_action(engine, "p1", "p4")
    _advance(engine)  # kills p4, -> DAY
    _advance(engine)  # -> VOTING
    _vote(engine, "p2", "p5")
    _vote(engine, "p3", "p5")
    _advance(engine)  # -> ELIMINATION, p5 eliminated
    _advance(engine)  # -> NIGHT round 2 (mafia 1 vs town 2, game continues)

    assert engine.phase == MafiaPhase.NIGHT
    with pytest.raises(InvalidGameStateError):
        _night_action(engine, "p4", "p2")


def test_vote_rejected_outside_voting_phase():
    engine = _standard_engine()

    with pytest.raises(InvalidGameStateError):
        _vote(engine, "p1", "p2")


def test_voting_eliminates_plurality_target():
    engine = _standard_engine()
    _advance(engine)  # -> DAY
    _advance(engine)  # -> VOTING

    _vote(engine, "p1", "p4")
    _vote(engine, "p2", "p4")
    _vote(engine, "p3", "p4")
    _vote(engine, "p4", "p1")

    events = _advance(engine)  # -> ELIMINATION

    result = next(e for e in events if isinstance(e, EliminationResultEvent))
    assert result.eliminated_player_id == "p4"
    assert engine.is_alive("p4") is False


def test_voting_tie_results_in_no_elimination():
    engine = _standard_engine()
    _advance(engine)  # -> DAY
    _advance(engine)  # -> VOTING

    _vote(engine, "p1", "p3")
    _vote(engine, "p2", "p3")
    _vote(engine, "p3", "p1")
    _vote(engine, "p4", "p1")

    events = _advance(engine)  # -> ELIMINATION

    result = next(e for e in events if isinstance(e, EliminationResultEvent))
    assert result.eliminated_player_id is None
    assert engine.is_alive("p1") is True
    assert engine.is_alive("p3") is True


def test_town_wins_when_all_mafia_eliminated():
    engine = _standard_engine()
    _night_action(engine, "p2", "p2")  # doctor protects self, mafia abstains
    _advance(engine)  # -> DAY, no kill
    _advance(engine)  # -> VOTING

    _vote(engine, "p2", "p1")
    _vote(engine, "p3", "p1")
    _vote(engine, "p4", "p1")

    _advance(engine)  # -> ELIMINATION, p1 (mafia) voted out
    assert engine.is_alive("p1") is False

    events = _advance(engine)  # -> GAME_OVER, win check

    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_team == "town"
    assert engine.phase == MafiaPhase.GAME_OVER


def test_mafia_wins_when_reaching_parity_after_night_kill():
    engine = MafiaGameEngine("XYZ12")
    players = ["p1", "p2", "p3"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "detective", "p3": "doctor"})

    _night_action(engine, "p1", "p2")  # mafia kills the detective, doctor doesn't protect

    events = _advance(engine)  # mafia(1) vs town(1) -> immediate GAME_OVER from NIGHT

    assert engine.phase == MafiaPhase.GAME_OVER
    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_team == "mafia"
    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id == "p2"


def test_advance_phase_rejected_after_game_over():
    engine = MafiaGameEngine("XYZ12")
    players = ["p1", "p2", "p3"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "detective", "p3": "doctor"})
    _night_action(engine, "p1", "p2")
    _advance(engine)  # -> GAME_OVER

    with pytest.raises(InvalidGameStateError):
        _advance(engine)


def test_phase_snapshot_reflects_alive_players_after_elimination():
    engine = _standard_engine()
    _night_action(engine, "p1", "p4")
    _advance(engine)  # kills p4, -> DAY

    snapshot = engine.phase_snapshot()
    assert snapshot["alive_player_ids"] == ["p1", "p2", "p3"]
