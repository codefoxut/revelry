import random

from app.games.mafia.role_assignment import assign_roles
from app.games.mafia.roles import Team

_PLAYERS = [f"p{i}" for i in range(12)]


def test_every_player_gets_exactly_one_role():
    assignment = assign_roles(_PLAYERS, random.Random(1))
    assert set(assignment.keys()) == set(_PLAYERS)


def test_composition_scales_with_player_count():
    for player_count, expected_mafia in ((4, 1), (5, 1), (8, 2), (12, 3)):
        players = [f"p{i}" for i in range(player_count)]
        assignment = assign_roles(players, random.Random(0))
        teams = [role.team for role in assignment.values()]
        assert teams.count(Team.MAFIA) == expected_mafia


def test_four_players_get_exactly_one_of_each_role():
    assignment = assign_roles(["p1", "p2", "p3", "p4"], random.Random(0))
    keys = sorted(role.key for role in assignment.values())
    assert keys == ["detective", "doctor", "mafia", "villager"]


def test_assignment_is_deterministic_for_a_seeded_rng():
    first = assign_roles(_PLAYERS, random.Random(42))
    second = assign_roles(_PLAYERS, random.Random(42))
    assert {pid: role.key for pid, role in first.items()} == {pid: role.key for pid, role in second.items()}
