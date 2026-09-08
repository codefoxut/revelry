import random

import pytest

from app.games.spyfall.location_assignment import assign_roles
from app.games.spyfall.locations import LOCATION_REGISTRY
from app.platform.exceptions import InvalidGameSettingsError

_PLAYER_IDS = ["p1", "p2", "p3", "p4", "p5"]


def test_assign_roles_picks_exactly_one_spy():
    location_key, roles_by_player = assign_roles(_PLAYER_IDS, random.Random(1))

    spies = [player_id for player_id, role in roles_by_player.items() if role is None]
    assert len(spies) == 1
    assert location_key in LOCATION_REGISTRY


def test_assign_roles_gives_every_non_spy_a_role_from_the_chosen_location():
    location_key, roles_by_player = assign_roles(_PLAYER_IDS, random.Random(2))
    location = LOCATION_REGISTRY[location_key]

    for player_id, role in roles_by_player.items():
        if role is not None:
            assert role in location.roles


def test_assign_roles_covers_every_active_player():
    location_key, roles_by_player = assign_roles(_PLAYER_IDS, random.Random(3))

    assert set(roles_by_player) == set(_PLAYER_IDS)


def test_assign_roles_cycles_roles_when_more_players_than_roles():
    many_players = [f"p{i}" for i in range(12)]
    _, roles_by_player = assign_roles(many_players, random.Random(4))

    non_spy_roles = [role for role in roles_by_player.values() if role is not None]
    assert len(non_spy_roles) == 11  # every player but the spy


def test_assign_roles_respects_enabled_location_keys():
    location_key, _ = assign_roles(_PLAYER_IDS, random.Random(5), enabled_location_keys=frozenset({"airplane"}))

    assert location_key == "airplane"


def test_assign_roles_raises_on_empty_enabled_location_keys():
    with pytest.raises(InvalidGameSettingsError):
        assign_roles(_PLAYER_IDS, random.Random(6), enabled_location_keys=frozenset())


def test_assign_roles_raises_on_unknown_enabled_location_key():
    with pytest.raises(InvalidGameSettingsError):
        assign_roles(_PLAYER_IDS, random.Random(7), enabled_location_keys=frozenset({"mars_base"}))


def test_assign_roles_is_deterministic_given_the_same_rng_seed():
    first = assign_roles(_PLAYER_IDS, random.Random(42))
    second = assign_roles(_PLAYER_IDS, random.Random(42))

    assert first == second
