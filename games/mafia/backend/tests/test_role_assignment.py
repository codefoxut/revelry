import random

import pytest

from app.games.mafia.role_assignment import assign_roles, build_composition, clamp_mafia_count
from app.games.mafia.roles import Team
from app.platform.exceptions import InvalidGameSettingsError

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


def test_clamp_mafia_count_defaults_to_a_quarter_of_players():
    assert clamp_mafia_count(4, None) == 1
    assert clamp_mafia_count(8, None) == 2
    assert clamp_mafia_count(12, None) == 3


def test_clamp_mafia_count_enforces_at_least_one():
    assert clamp_mafia_count(4, 0) == 1
    assert clamp_mafia_count(4, -5) == 1


def test_clamp_mafia_count_never_leaves_fewer_than_two_non_mafia():
    # 6 players: max_mafia = max(1, min(6 // 3, 6 - 2)) = max(1, min(2, 4)) = 2
    assert clamp_mafia_count(6, 100) == 2


def test_clamp_mafia_count_respects_a_valid_request():
    assert clamp_mafia_count(12, 3) == 3


def test_build_composition_fills_remaining_slots_with_villagers():
    roles = build_composition(6, 1, frozenset({"detective", "doctor"}))
    keys = sorted(role.key for role in roles)
    assert keys == ["detective", "doctor", "mafia", "villager", "villager", "villager"]


def test_build_composition_godfather_replaces_a_mafia_slot_not_adds_to_it():
    roles = build_composition(6, 2, frozenset({"godfather"}))
    keys = sorted(role.key for role in roles)
    # mafia_count=2 total mafia-team slots: one becomes godfather, the other
    # stays plain mafia -- not 2 mafia + 1 godfather.
    assert keys == ["godfather", "mafia", "villager", "villager", "villager", "villager"]


def test_build_composition_overflow_raises_instead_of_dropping_roles():
    with pytest.raises(InvalidGameSettingsError):
        build_composition(3, 1, frozenset({"detective", "doctor", "bodyguard"}))


def test_build_composition_exact_fit_does_not_raise():
    roles = build_composition(3, 1, frozenset({"detective", "doctor"}))
    keys = sorted(role.key for role in roles)
    assert keys == ["detective", "doctor", "mafia"]


def test_assign_roles_honors_explicit_mafia_count_and_enabled_roles():
    players = [f"p{i}" for i in range(6)]
    assignment = assign_roles(
        players, random.Random(0), mafia_count=2, enabled_role_keys=frozenset({"godfather"})
    )
    keys = sorted(role.key for role in assignment.values())
    assert keys == ["godfather", "mafia", "villager", "villager", "villager", "villager"]


def test_assign_roles_overflow_raises_invalid_game_settings_error():
    players = ["p1", "p2", "p3"]
    with pytest.raises(InvalidGameSettingsError):
        assign_roles(
            players,
            random.Random(0),
            mafia_count=1,
            enabled_role_keys=frozenset({"detective", "doctor", "bodyguard"}),
        )


def test_build_composition_terrorist_adds_a_slot_not_replaces_a_mafia_slot():
    roles = build_composition(6, 2, frozenset({"terrorist"}))
    keys = sorted(role.key for role in roles)
    # mafia_count=2 stays two plain mafia; terrorist is additive, unlike
    # godfather which substitutes for one of the mafia_count slots.
    assert keys == ["mafia", "mafia", "terrorist", "villager", "villager", "villager"]


def test_build_composition_traitor_is_an_additive_neutral_slot():
    roles = build_composition(6, 1, frozenset({"traitor"}))
    keys = sorted(role.key for role in roles)
    assert keys == ["mafia", "traitor", "villager", "villager", "villager", "villager"]
