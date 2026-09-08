from app.games.spyfall.locations import LOCATION_REGISTRY


def test_registry_has_at_least_twenty_locations():
    assert len(LOCATION_REGISTRY) >= 20


def test_every_location_key_matches_its_own_key_field():
    for key, location in LOCATION_REGISTRY.items():
        assert location.key == key


def test_every_location_has_exactly_seven_roles():
    for location in LOCATION_REGISTRY.values():
        assert len(location.roles) == 7


def test_every_location_has_a_non_empty_display_name():
    for location in LOCATION_REGISTRY.values():
        assert location.display_name


def test_roles_within_a_location_are_unique():
    for location in LOCATION_REGISTRY.values():
        assert len(set(location.roles)) == len(location.roles)


def test_location_keys_are_unique():
    keys = [location.key for location in LOCATION_REGISTRY.values()]
    assert len(keys) == len(set(keys))
