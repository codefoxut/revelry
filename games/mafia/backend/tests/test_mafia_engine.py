import asyncio

import pytest

from app.games.mafia.commands import AdvancePhaseCommand, StartGameCommand
from app.games.mafia.engine import MafiaGameEngine
from app.games.mafia.events import RoleAssignedEvent
from app.games.mafia.phases import MafiaPhase
from app.games.mafia.roles import Team
from app.platform.exceptions import InvalidGameStateError

_PLAYERS = ["p1", "p2", "p3", "p4"]


def test_starting_moves_to_night_round_one():
    engine = MafiaGameEngine("ABCDE")
    events = asyncio.run(
        engine.handle_command(StartGameCommand(player_id="host", active_player_ids=_PLAYERS))
    )

    assert engine.phase == MafiaPhase.NIGHT
    assert engine.round_number == 1
    assert events[0].phase == MafiaPhase.NIGHT
    assert events[0].round_number == 1


def test_starting_assigns_every_player_exactly_one_role():
    engine = MafiaGameEngine("ABCDE")
    events = asyncio.run(
        engine.handle_command(StartGameCommand(player_id="host", active_player_ids=_PLAYERS))
    )

    role_events = [event for event in events if isinstance(event, RoleAssignedEvent)]
    assert {event.player_id for event in role_events} == set(_PLAYERS)
    for player_id in _PLAYERS:
        role = engine.role_for(player_id)
        assert role is not None
        assert role.team in (Team.TOWN, Team.MAFIA)

    teams = [engine.role_for(player_id).team for player_id in _PLAYERS]  # type: ignore[union-attr]
    assert teams.count(Team.MAFIA) == 1


def test_advancing_before_start_is_rejected():
    engine = MafiaGameEngine("ABCDE")
    with pytest.raises(InvalidGameStateError):
        asyncio.run(engine.handle_command(AdvancePhaseCommand(player_id="host")))


def test_full_cycle_increments_round_on_return_to_night():
    engine = MafiaGameEngine("ABCDE")
    asyncio.run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=_PLAYERS)))

    asyncio.run(engine.handle_command(AdvancePhaseCommand(player_id="host")))  # -> DAY
    assert engine.phase == MafiaPhase.DAY
    assert engine.round_number == 1

    asyncio.run(engine.handle_command(AdvancePhaseCommand(player_id="host")))  # -> VOTING
    assert engine.phase == MafiaPhase.VOTING

    asyncio.run(engine.handle_command(AdvancePhaseCommand(player_id="host")))  # -> ELIMINATION
    assert engine.phase == MafiaPhase.ELIMINATION
    assert engine.round_number == 1

    asyncio.run(engine.handle_command(AdvancePhaseCommand(player_id="host")))  # -> NIGHT (round 2)
    assert engine.phase == MafiaPhase.NIGHT
    assert engine.round_number == 2


def test_phase_snapshot_matches_current_state():
    engine = MafiaGameEngine("ABCDE")
    asyncio.run(engine.handle_command(StartGameCommand(player_id="host", active_player_ids=_PLAYERS)))

    assert engine.phase_snapshot() == {
        "phase": "night",
        "round_number": 1,
        "alive_player_ids": sorted(_PLAYERS),
    }
