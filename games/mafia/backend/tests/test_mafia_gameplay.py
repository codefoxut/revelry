import asyncio
import random

import pytest

from app.games.mafia.commands import (
    AdvancePhaseCommand,
    CastVoteCommand,
    LockNightActionCommand,
    RevealMayorCommand,
    StartGameCommand,
    SubmitNightActionCommand,
    WithdrawBombCommand,
)
from app.games.mafia.conflict_resolution import ConflictResolution
from app.games.mafia.day_tie_resolution import DayTieResolution
from app.games.mafia.engine import MafiaGameEngine
from app.games.mafia.events import (
    EliminationResultEvent,
    GameOverEvent,
    InvestigationResultEvent,
    MafiaTargetsUpdatedEvent,
    MayorRevealedEvent,
    NightResultEvent,
    TerroristBombStatusEvent,
)
from app.games.mafia.phases import MafiaPhase
from app.games.mafia.role_assignment import assign_roles
from app.games.mafia.roles import ROLE_REGISTRY, NightActionKind
from app.platform.exceptions import InvalidGameStateError

_PLAYERS = ["p1", "p2", "p3", "p4"]


def _start(
    engine,
    players=_PLAYERS,
    conflict_resolution=ConflictResolution.KILL_ANY,
    day_tie_resolution=DayTieResolution.NO_ELIMINATION,
):
    asyncio.run(
        engine.handle_command(
            StartGameCommand(
                player_id="host",
                active_player_ids=players,
                conflict_resolution=conflict_resolution,
                day_tie_resolution=day_tie_resolution,
            )
        )
    )


def _force_roles(engine, mapping):
    """Pin each player's role for a deterministic test scenario, bypassing
    the random assignment step. Also recomputes vigilante charges the same
    way `_start_game` does, since the forced roles differ from whatever the
    initial random assignment produced.
    """
    engine._roles = {player_id: ROLE_REGISTRY[role_key] for player_id, role_key in mapping.items()}
    engine._vigilante_uses_remaining = {
        player_id: role.max_uses
        for player_id, role in engine._roles.items()
        if role.night_action_kind is NightActionKind.VIGILANTE_KILL and role.max_uses is not None
    }


def _reveal_mayor(engine, player_id):
    return asyncio.run(engine.handle_command(RevealMayorCommand(player_id=player_id)))


def _advance(engine):
    return asyncio.run(engine.handle_command(AdvancePhaseCommand(player_id="host")))


def _night_action(engine, player_id, target_id):
    return asyncio.run(
        engine.handle_command(SubmitNightActionCommand(player_id=player_id, target_player_id=target_id))
    )


def _lock(engine, player_id):
    return asyncio.run(engine.handle_command(LockNightActionCommand(player_id=player_id)))


def _withdraw(engine, player_id):
    return asyncio.run(engine.handle_command(WithdrawBombCommand(player_id=player_id)))


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
    assert night_result.eliminated_player_ids == ["p4"]
    assert engine.is_alive("p4") is False
    assert engine.phase == MafiaPhase.DAY


def test_doctor_protection_cancels_mafia_kill():
    engine = _standard_engine()
    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p4")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == []
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
    assert night_result.eliminated_player_ids == ["p5"]
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
    assert night_result.eliminated_player_ids != []


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
    assert night_result.eliminated_player_ids == []
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
    assert night_result.eliminated_player_ids == [expected_victim]


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
    assert night_result.eliminated_player_ids == []
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
    assert night_result.eliminated_player_ids == ["p2"]


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


# ---- Bodyguard ----


def test_bodyguard_dies_instead_of_the_player_they_guard():
    engine = MafiaGameEngine("BG01")
    players = ["p1", "p2", "p3", "p4"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "bodyguard", "p3": "villager", "p4": "villager"})

    _night_action(engine, "p1", "p3")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p3")  # bodyguard guards mafia's actual target

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == ["p2"]
    assert engine.is_alive("p2") is False
    assert engine.is_alive("p3") is True


def test_bodyguard_survives_when_guarding_a_different_player_than_mafias_target():
    engine = MafiaGameEngine("BG02")
    players = ["p1", "p2", "p3", "p4"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "bodyguard", "p3": "villager", "p4": "villager"})

    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p3")  # guarding someone mafia didn't target

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == ["p4"]
    assert engine.is_alive("p2") is True


# ---- Vigilante ----


def test_vigilante_kill_resolves_independently_of_mafia():
    engine = MafiaGameEngine("VIG01")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "vigilante", "p3": "villager", "p4": "villager", "p5": "villager"},
    )

    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p5")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert sorted(night_result.eliminated_player_ids) == ["p4", "p5"]
    assert engine._vigilante_uses_remaining["p2"] == 1


def test_vigilante_charge_only_decremented_once_despite_changing_target():
    engine = MafiaGameEngine("VIG02")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "vigilante", "p3": "villager", "p4": "villager", "p5": "villager"},
    )

    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p3")  # first pick
    _night_action(engine, "p2", "p5")  # changes their mind before advancing

    _advance(engine)

    assert engine._vigilante_uses_remaining["p2"] == 1


def test_vigilante_action_rejected_once_out_of_uses():
    engine = MafiaGameEngine("VIG03")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "vigilante", "p3": "villager", "p4": "villager", "p5": "villager"},
    )
    engine._vigilante_uses_remaining["p2"] = 0

    with pytest.raises(InvalidGameStateError):
        _night_action(engine, "p2", "p3")


# ---- Escort ----


def test_escort_blocking_a_locked_mafia_member_breaks_the_teams_unanimity():
    engine = MafiaGameEngine("ESC01", rng=random.Random(3))
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {
            "p1": "mafia",
            "p2": "mafia",
            "p3": "escort",
            "p4": "villager",
            "p5": "villager",
            "p6": "villager",
        },
    )

    probe_rng = random.Random(3)
    assign_roles(players, probe_rng)
    expected_victim = probe_rng.choice(players)

    _night_action(engine, "p1", "p4")
    _night_action(engine, "p2", "p4")
    _lock(engine, "p1")
    _lock(engine, "p2")
    _night_action(engine, "p3", "p1")  # escort blocks p1, breaking the lock

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    # Losing p1's lock means the team no longer has consensus, so the night
    # falls back to KILL_ANY instead of killing their previously-agreed p4.
    assert night_result.eliminated_player_ids == [expected_victim]


def test_escort_blocking_the_doctor_lets_mafias_kill_through():
    engine = MafiaGameEngine("ESC02")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "doctor", "p3": "escort", "p4": "villager", "p5": "villager"},
    )

    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p4")  # doctor tries to protect p4
    _night_action(engine, "p3", "p2")  # escort blocks the doctor

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == ["p4"]


# ---- Serial Killer ----


def test_serial_killer_kill_is_independent_and_immune_to_bodyguard_redirect():
    engine = MafiaGameEngine("SK01")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players)
    _force_roles(
        engine,
        {
            "p1": "mafia",
            "p2": "bodyguard",
            "p3": "serial_killer",
            "p4": "villager",
            "p5": "villager",
        },
    )

    _night_action(engine, "p1", "p4")
    _lock(engine, "p1")
    _night_action(engine, "p2", "p4")  # bodyguard guards mafia's target -> redirected to p2
    _night_action(engine, "p3", "p5")  # serial killer acts independently

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert sorted(night_result.eliminated_player_ids) == ["p2", "p5"]
    assert engine.is_alive("p4") is True
    # The serial killer is a living hostile neutral, so the game continues
    # even though the remaining town/mafia counts alone might otherwise end it.
    assert engine.phase == MafiaPhase.DAY


def test_serial_killer_wins_as_the_last_player_standing():
    engine = MafiaGameEngine("SK02")
    _force_roles(engine, {"p1": "mafia", "p2": "serial_killer"})
    engine._alive = {"p1": False, "p2": True}

    assert engine._check_win() == "serial_killer"


def test_hostile_neutral_alive_blocks_town_win_even_with_no_mafia_left():
    engine = MafiaGameEngine("SK03")
    _force_roles(engine, {"p1": "serial_killer", "p2": "villager"})
    engine._alive = {"p1": True, "p2": True}

    assert engine._check_win() is None


def test_draw_when_only_a_non_hostile_neutral_remains():
    engine = MafiaGameEngine("SURV01")
    _force_roles(engine, {"p1": "survivor"})
    engine._alive = {"p1": True}

    assert engine._check_win() == "draw"


# ---- Godfather ----


def test_godfather_participates_in_the_mafia_kill_and_lock_like_mafia():
    engine = MafiaGameEngine("GF01")
    players = ["p1", "p2", "p3", "p4", "p5", "p6"]
    _start(engine, players)
    _force_roles(
        engine,
        {
            "p1": "godfather",
            "p2": "mafia",
            "p3": "doctor",
            "p4": "detective",
            "p5": "villager",
            "p6": "villager",
        },
    )

    _night_action(engine, "p1", "p5")
    _night_action(engine, "p2", "p5")
    _lock(engine, "p1")
    _lock(engine, "p2")

    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == ["p5"]


def test_godfather_investigates_as_town_despite_being_mafia():
    engine = MafiaGameEngine("GF02")
    players = ["p1", "p2", "p3", "p4"]
    _start(engine, players)
    _force_roles(engine, {"p1": "godfather", "p2": "detective", "p3": "villager", "p4": "villager"})

    events = _night_action(engine, "p2", "p1")

    assert events == [InvestigationResultEvent(player_id="p2", target_player_id="p1", team="town")]


# ---- Mayor ----


def test_mayor_reveal_doubles_their_vote_weight():
    engine = MafiaGameEngine("MAY01")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players, conflict_resolution=ConflictResolution.NO_KILL)
    _force_roles(
        engine,
        {"p1": "mayor", "p2": "mafia", "p3": "villager", "p4": "villager", "p5": "villager"},
    )
    _advance(engine)  # -> DAY (mafia never locked a target, NO_KILL -> no death)
    _advance(engine)  # -> VOTING

    _reveal_mayor(engine, "p1")
    _vote(engine, "p1", "p3")  # mayor's vote now counts as 2
    _vote(engine, "p4", "p5")  # a single ordinary vote

    events = _advance(engine)  # -> ELIMINATION

    result = next(e for e in events if isinstance(e, EliminationResultEvent))
    assert result.eliminated_player_id == "p3"


def test_mayor_reveal_is_idempotent():
    engine = MafiaGameEngine("MAY02")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players, conflict_resolution=ConflictResolution.NO_KILL)
    _force_roles(
        engine,
        {"p1": "mayor", "p2": "mafia", "p3": "villager", "p4": "villager", "p5": "villager"},
    )
    _advance(engine)  # -> DAY

    first = _reveal_mayor(engine, "p1")
    assert first == [MayorRevealedEvent(player_id="p1")]

    second = _reveal_mayor(engine, "p1")
    assert second == []
    assert engine._mayor_revealed is True


def test_mayor_reveal_rejected_outside_day_or_voting_phase():
    engine = MafiaGameEngine("MAY03")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players)
    _force_roles(
        engine,
        {"p1": "mayor", "p2": "mafia", "p3": "villager", "p4": "villager", "p5": "villager"},
    )

    with pytest.raises(InvalidGameStateError):
        _reveal_mayor(engine, "p1")  # still NIGHT


# ---- Day tie resolution ----


def test_day_tie_resolution_random_among_tied_picks_one_of_the_tied_targets():
    engine = MafiaGameEngine("TIE01", rng=random.Random(5))
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(
        engine,
        players,
        conflict_resolution=ConflictResolution.NO_KILL,
        day_tie_resolution=DayTieResolution.RANDOM_AMONG_TIED,
    )
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "villager", "p3": "villager", "p4": "villager", "p5": "villager"},
    )
    _advance(engine)  # -> DAY (mafia never locked a target, NO_KILL -> no death)
    _advance(engine)  # -> VOTING

    probe_rng = random.Random(5)
    assign_roles(players, probe_rng)
    expected = probe_rng.choice(sorted(["p4", "p5"]))

    _vote(engine, "p2", "p4")
    _vote(engine, "p3", "p5")

    events = _advance(engine)  # -> ELIMINATION

    result = next(e for e in events if isinstance(e, EliminationResultEvent))
    assert result.eliminated_player_id == expected


# ---- Jester ----


def test_jester_wins_when_eliminated_by_day_vote():
    engine = MafiaGameEngine("JEST01")
    players = ["p1", "p2", "p3", "p4", "p5"]
    _start(engine, players, conflict_resolution=ConflictResolution.NO_KILL)
    _force_roles(
        engine,
        {"p1": "jester", "p2": "mafia", "p3": "villager", "p4": "villager", "p5": "villager"},
    )
    _advance(engine)  # -> DAY (mafia never locked a target, NO_KILL -> no death)
    _advance(engine)  # -> VOTING

    _vote(engine, "p3", "p1")
    _vote(engine, "p4", "p1")
    _vote(engine, "p5", "p1")

    _advance(engine)  # -> ELIMINATION, p1 (jester) voted out
    events = _advance(engine)  # -> GAME_OVER

    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_team == "jester"
    assert engine.phase == MafiaPhase.GAME_OVER


def test_jester_killed_at_night_does_not_grant_a_jester_win():
    engine = MafiaGameEngine("JEST02")
    players = ["p1", "p2", "p3", "p4"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "jester", "p3": "villager", "p4": "villager"})

    _night_action(engine, "p1", "p2")
    _lock(engine, "p1")

    events = _advance(engine)

    assert engine.phase == MafiaPhase.DAY
    game_over_events = [e for e in events if isinstance(e, GameOverEvent)]
    assert game_over_events == []


# ---- Terrorist ----


def _terrorist_engine(room_code="TER01", players=None, conflict_resolution=ConflictResolution.NO_KILL):
    players = players or ["p1", "p2", "p3", "p4", "p5"]
    engine = MafiaGameEngine(room_code)
    _start(engine, players, conflict_resolution=conflict_resolution)
    _force_roles(
        engine,
        {"p1": "mafia", "p2": "terrorist", "p3": "doctor", "p4": "villager", "p5": "villager"},
    )
    return engine


def test_terrorist_plant_does_not_kill_the_same_night():
    engine = _terrorist_engine()

    _night_action(engine, "p2", "p4")
    events = _advance(engine)  # -> DAY, round 1

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == []
    assert engine.is_alive("p4") is True
    assert engine._pending_bomb_target == "p4"

    bomb_status = next(e for e in events if isinstance(e, TerroristBombStatusEvent))
    assert bomb_status == TerroristBombStatusEvent(player_id="p2", pending=True, target_player_id="p4")


def test_terrorist_bomb_detonates_during_the_following_nights_resolution():
    engine = _terrorist_engine()

    _night_action(engine, "p2", "p4")
    _advance(engine)  # -> DAY, round 1 (no death, bomb armed)
    _advance(engine)  # -> VOTING
    _advance(engine)  # -> ELIMINATION (no votes cast)
    _advance(engine)  # -> NIGHT, round 2

    events = _advance(engine)  # -> DAY, round 2: bomb detonates, no fresh plant this round

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == ["p4"]
    assert engine.is_alive("p4") is False
    assert engine._pending_bomb_target is None

    bomb_status = next(e for e in events if isinstance(e, TerroristBombStatusEvent))
    assert bomb_status == TerroristBombStatusEvent(player_id="p2", pending=False, target_player_id=None)


def test_terrorist_bomb_target_can_be_saved_by_doctor():
    engine = _terrorist_engine()

    _night_action(engine, "p2", "p4")
    _advance(engine)  # -> DAY, round 1
    _advance(engine)  # -> VOTING
    _advance(engine)  # -> ELIMINATION
    _advance(engine)  # -> NIGHT, round 2

    _night_action(engine, "p3", "p4")  # doctor protects the bomb's target this round
    events = _advance(engine)

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == []
    assert engine.is_alive("p4") is True


def test_terrorist_withdraw_cancels_detonation_and_frees_the_slot_for_a_later_replant():
    engine = _terrorist_engine()

    _night_action(engine, "p2", "p4")
    _advance(engine)  # -> DAY, round 1
    _advance(engine)  # -> VOTING
    _advance(engine)  # -> ELIMINATION
    _advance(engine)  # -> NIGHT, round 2

    _withdraw(engine, "p2")
    events = _advance(engine)  # -> DAY, round 2: withdrawal cancels detonation

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == []
    assert engine.is_alive("p4") is True
    assert engine._pending_bomb_target is None

    _advance(engine)  # -> VOTING
    _advance(engine)  # -> ELIMINATION
    _advance(engine)  # -> NIGHT, round 3

    # The slot is free again, so a fresh plant is accepted.
    _night_action(engine, "p2", "p5")
    assert engine._pending_bomb_target is None  # not armed until this round resolves
    events = _advance(engine)  # -> DAY, round 3

    night_result = next(e for e in events if isinstance(e, NightResultEvent))
    assert night_result.eliminated_player_ids == []
    assert engine._pending_bomb_target == "p5"


def test_terrorist_cannot_plant_a_second_bomb_while_one_is_pending():
    engine = _terrorist_engine()

    _night_action(engine, "p2", "p4")
    _advance(engine)  # -> DAY, round 1: bomb now armed and pending

    with pytest.raises(InvalidGameStateError):
        _night_action(engine, "p2", "p5")


def test_withdraw_bomb_rejected_when_no_bomb_is_pending():
    engine = _terrorist_engine()

    with pytest.raises(InvalidGameStateError):
        _withdraw(engine, "p2")


def test_withdraw_bomb_rejected_for_non_terrorist():
    engine = _terrorist_engine()

    with pytest.raises(InvalidGameStateError):
        _withdraw(engine, "p1")  # p1 is mafia, not the terrorist


def test_terrorist_night_action_does_not_appear_in_mafia_picks_and_does_not_block_the_lock():
    engine = _terrorist_engine(conflict_resolution=ConflictResolution.NO_KILL)

    _night_action(engine, "p1", "p4")  # mafia's only member picks a target
    events = _night_action(engine, "p2", "p5")  # terrorist plants independently

    assert events == []  # no MafiaTargetsUpdatedEvent leaked to the terrorist's action

    # Mafia (a single member here) can still lock despite the terrorist never
    # locking anything -- the terrorist isn't part of the consensus pool.
    lock_events = _lock(engine, "p1")
    picks_event = next(e for e in lock_events if isinstance(e, MafiaTargetsUpdatedEvent))
    assert [pick.player_id for pick in picks_event.picks] == ["p1"]


def test_mafia_win_math_counts_a_living_terrorist_toward_mafia():
    engine = MafiaGameEngine("TER02")
    _force_roles(engine, {"p1": "terrorist", "p2": "villager"})
    engine._alive = {"p1": True, "p2": True}

    # Parity (1 mafia-aligned vs 1 town) is a mafia win, same as plain mafia.
    assert engine._check_win() == "mafia"


def test_detective_investigates_terrorist_as_mafia():
    engine = MafiaGameEngine("TER03")
    players = ["p1", "p2", "p3", "p4"]
    _start(engine, players)
    _force_roles(engine, {"p1": "terrorist", "p2": "detective", "p3": "villager", "p4": "villager"})

    events = _night_action(engine, "p2", "p1")

    assert events == [InvestigationResultEvent(player_id="p2", target_player_id="p1", team="mafia")]


# ---- Traitor ----


def test_traitor_has_no_effect_on_win_math():
    engine = MafiaGameEngine("TRA01")
    _force_roles(engine, {"p1": "mafia", "p2": "traitor", "p3": "villager"})
    engine._alive = {"p1": True, "p2": True, "p3": True}

    # 1 mafia vs 1 town (traitor doesn't count toward either) -> mafia wins
    # on parity, identical to the traitor not existing at all.
    assert engine._check_win() == "mafia"


def test_traitor_has_no_night_action():
    engine = MafiaGameEngine("TRA02")
    players = ["p1", "p2", "p3", "p4"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "traitor", "p3": "villager", "p4": "villager"})

    with pytest.raises(InvalidGameStateError):
        _night_action(engine, "p2", "p3")


def test_detective_investigates_traitor_as_town():
    engine = MafiaGameEngine("TRA03")
    players = ["p1", "p2", "p3", "p4"]
    _start(engine, players)
    _force_roles(engine, {"p1": "mafia", "p2": "traitor", "p3": "detective", "p4": "villager"})

    events = _night_action(engine, "p3", "p2")

    assert events == [InvestigationResultEvent(player_id="p3", target_player_id="p2", team="town")]
