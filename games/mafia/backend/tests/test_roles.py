from app.games.mafia.roles import DETECTIVE, DOCTOR, MAFIA_ROLE, ROLE_REGISTRY, VILLAGER, Team


def test_registry_contains_all_four_roles():
    assert set(ROLE_REGISTRY.keys()) == {"villager", "mafia", "detective", "doctor"}
    assert ROLE_REGISTRY["villager"] is VILLAGER
    assert ROLE_REGISTRY["mafia"] is MAFIA_ROLE
    assert ROLE_REGISTRY["detective"] is DETECTIVE
    assert ROLE_REGISTRY["doctor"] is DOCTOR


def test_mafia_is_the_only_mafia_team_role():
    assert MAFIA_ROLE.team == Team.MAFIA
    for role in (VILLAGER, DETECTIVE, DOCTOR):
        assert role.team == Team.TOWN


def test_only_villager_has_no_night_action():
    assert VILLAGER.acts_at_night is False
    for role in (MAFIA_ROLE, DETECTIVE, DOCTOR):
        assert role.acts_at_night is True
