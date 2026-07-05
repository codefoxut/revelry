import asyncio
import random

import pytest

from app.games.mafia.commands import (
    AdvancePhaseCommand,
    CastVoteCommand,
    LockNightActionCommand,
    StartGameCommand,
    SubmitNightActionCommand,
)
from app.games.mafia.conflict_resolution import ConflictResolution
from app.games.mafia.engine import MafiaGameEngine
from app.games.mafia.events import (
    EliminationResultEvent,
    GameOverEvent,
    InvestigationResultEvent,
    MafiaTargetsUpdatedEvent,
    NightResultEvent,
)
from app.games.mafia.phases import MafiaPhase
from app.games.mafia.role_assignment import assign_roles
from app.games.mafia.roles import ROLE_REGISTRY
from app.platform.exceptions import InvalidGameStateError

_PLAYERS = ["p1", "p2", "p3", "p4"]


def _start(engine, players=_PLAYERS, conflict_resolution=ConflictResolution.KILL_ANY):
    asyncio.run(
        engine.handle_command(
            StartGameCommand(player_id="host", active_player_ids=players, conflict_resolution=conflict_resolution)
        )
    )


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


def _lock(engine, player_id):
    return asyncio.run(engine.handle_command(LockNightActionCommand(player_id=player_id)))


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
    _lock(engine, "p1")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id == "p4"
    assert engine.is_alive("p4") is False
    assert engine.phase == MafiaPhase.DAY


def test_doctor_protection_cancels_mafia_kill():
    engine = _standard_engine()
    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p4")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id is None
    assert engine.is_alive("p4") is True


def test_night_action_broadcasts_live_pick_to_mafia_team():
    engine = _standard_engine()

    events = _night_action(engine, "p1", "p4")

    picks_event = next(e for e in events if isinstance(e, MafiaTargetsUpdatedEvent))
    assert len(picks_event.picks) == 1
    pick = picks_event.picks[0]
    assert pick.player_id == "p1"
    assert pick.target_player_id == "p4"
    assert pick.locked is False


def test_changing_target_after_lock_unlocks_it():
    engine = _standard_engine()
    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")

    events = _night_action(engine, "p1", "p3")

    picks_event = next(e for e in events if isinstance(e, MafiaTargetsUpdatedEvent))
    pick = picks_event.picks[0]
    assert pick.target_player_id == "p3"
    assert pick.locked is False


def test_lock_without_a_target_is_rejected():
    engine = _standard_engine()

    with pytest.raises(InvalidGameStateError):
        _lock(engine, "p1")


def test_lock_by_non_mafia_is_rejected():
    engine = _standard_engine()

    with pytest.raises(InvalidGameStateError):
        _lock(engine, "p2")  # p2 is the doctor


def test_mafia_cannot_target_themselves():
    engine = _standard_engine()

    with pytest.raises(InvalidGameStateError):
        _night_action(engine, "p1", "p1")  # p1 is the mafia


def test_detective_cannot_target_themselves():
    engine = _standard_engine()

    with pytest.raises(InvalidGameStateError):
        _night_action(engine, "p3", "p3")  # p3 is the detective


def test_doctor_can_still_target_themselves():
    engine = _standard_engine()

    # Unlike mafia/detective, self-targeting is a valid doctor move (a
    # self-heal) and must not be rejected.
    events = _night_action(engine, "p2", "p2")  # p2 is the doctor

    assert events == []


def test_two_mafia_agreeing_and_locking_kills_the_agreed_target():
    engine = MafiaGameEngine("SIX01")
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "mafia", "p3": "doctor", "p4": "detective", "p5": "villager", "p6": "villager"},
    )

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p5")
    _lock(engine, "p1")
    _lock(engine, "p2")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id == "p5"
    assert engine.is_alive("p5") is False


def test_lock_rejected_when_mafia_disagree():
    engine = MafiaGameEngine("SIX02")
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "mafia", "p3": "doctor", "p4": "detective", "p5": "villager", "p6": "villager"},
    )

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p6")

    with pytest.raises(InvalidGameStateError):
        _lock(engine, "p1")
    with pytest.raises(InvalidGameStateError):
        _lock(engine, "p2")


def test_mafia_pick_change_clears_teammates_existing_lock():
    engine = MafiaGameEngine("SIX03")
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "mafia", "p3": "doctor", "p4": "detective", "p5": "villager", "p6": "villager"},
    )

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p5")
    _lock(engine, "p1")
    _lock(engine, "p2")

    _night_action(engine, "p2", "p6")  # p2 changes their mind after both had locked

    # p1's now-stale lock was cleared too, so re-locking while disagreeing
    # is rejected rather than resolving on p1's old agreement.
    with pytest.raises(InvalidGameStateError):
        _lock(engine, "p1")


def test_two_mafia_disagreeing_and_never_locking_falls_back_to_kill_any():
    engine = MafiaGameEngine("SIX04", rng=random.Random(1))
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "mafia", "p3": "doctor", "p4": "detective", "p5": "villager", "p6": "villager"},
    )

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p6")  # disagreement -> locking is impossible

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id is not None


def test_no_kill_mode_results_in_no_elimination_on_disagreement():
    engine = MafiaGameEngine("SIX05")
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players, conflict_resolution=ConflictResolution.NO_KILL)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "mafia", "p3": "doctor", "p4": "detective", "p5": "villager", "p6": "villager"},
    )

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p6")  # disagreement -> NO_KILL fallback

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id is None
    assert engine.is_alive("p5") is True
    assert engine.is_alive("p6") is True


def test_kill_any_fallback_pool_can_include_a_mafia_player():
    # Seeded so the disagreement fallback's random.choice lands on a mafia
    # player, confirming the pool is "all alive" and not "town only".
    engine = MafiaGameEngine("SIX06", rng=random.Random(7))
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "mafia", "p3": "doctor", "p4": "detective", "p5": "villager", "p6": "villager"},
    )

    probe_rng = random.Random(7)
    assign_roles(players, probe_rng)
    expected_victim = probe_rng.choice(players)
    assert engine.role_for(expected_victim).team.value == "mafia", "test seed must land on a mafia player"

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p6")  # disagreement -> KILL_ANY fallback

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id == expected_victim


def test_random_fallback_victim_can_still_be_saved_by_doctor():
    engine = MafiaGameEngine("SIX07", rng=random.Random(1))
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "mafia", "p3": "doctor", "p4": "detective", "p5": "villager", "p6": "villager"},
    )

    # Determine, via a probe rng seeded and advanced identically to the
    # engine's (role assignment consumes the seed first, before the night's
    # fallback choice), who the random fallback would pick (the pool is
    # every living player, mafia included), then have the doctor protect
    # exactly that player.
    probe_rng = random.Random(1)
    assign_roles(players, probe_rng)
    expected_victim = probe_rng.choice(players)

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p6")  # disagreement -> fallback, locking is impossible
    _night_action(engine, "p3", expected_victim)

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id is None
    assert engine.is_alive(expected_victim) is True


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
    _lock(engine, "p1")
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
    _night_action(engine, "p1", "p4")  # mafia targets p4, doctor protects p4 -> no night kill
    _lock(engine, "p1")
    _night_action(engine, "p2", "p4")
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
    _night_action(engine, "p1", "p4")  # mafia targets p4, doctor protects p4 -> no night kill
    _lock(engine, "p1")
    _night_action(engine, "p2", "p4")
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
    _night_action(engine, "p1", "p2")  # mafia targets p2, doctor protects p2 -> no night kill
    _lock(engine, "p1")
    _night_action(engine, "p2", "p2")  # doctor protects self
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
    reveal_by_player = {reveal.player_id: reveal for reveal in game_over.roles}
    assert set(reveal_by_player) == set(_PLAYERS)
    assert reveal_by_player["p1"].role_key == "mafia"
    assert reveal_by_player["p1"].team == "mafia"
    assert reveal_by_player["p2"].role_key == "doctor"
    assert reveal_by_player["p2"].team == "town"


def test_mafia_wins_when_reaching_parity_after_night_kill():
    engine = MafiaGameEngine("XYZ12")
    players = ["p1", "p2", "p3"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "detective", "p3": "doctor"})

    _night_action(engine, "p1", "p2")  # mafia kills the detective, doctor doesn't protect
    _lock(engine, "p1")

    events = _advance(engine)  # mafia(1) vs town(1) -> immediate GAME_OVER from NIGHT

    assert engine.phase == MafiaPhase.GAME_OVER
    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_team == "mafia"
    reveal_by_player = {reveal.player_id: reveal for reveal in game_over.roles}
    assert set(reveal_by_player) == set(players)
    assert reveal_by_player["p1"].role_key == "mafia"
    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_id == "p2"


def test_advance_phase_rejected_after_game_over():
    engine = MafiaGameEngine("XYZ12")
    players = ["p1", "p2", "p3"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "detective", "p3": "doctor"})
    _night_action(engine, "p1", "p2")
    _lock(engine, "p1")
    _advance(engine)  # -> GAME_OVER

    with pytest.raises(InvalidGameStateError):
        _advance(engine)


def test_phase_snapshot_reflects_alive_players_after_elimination():
    engine = _standard_engine()
    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _advance(engine)  # kills p4, -> DAY

    snapshot = engine.phase_snapshot()
    assert snapshot["alive_player_ids"] == ["p1", "p2", "p3"]
