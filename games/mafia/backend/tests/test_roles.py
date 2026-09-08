from app.games.mafia.roles import (
    BODYGUARD,
    DETECTIVE,
    DOCTOR,
    ESCORT,
    GODFATHER,
    JESTER,
    MAFIA_ROLE,
    MAYOR,
    ROLE_REGISTRY,
    SERIAL_KILLER,
    SURVIVOR,
    TERRORIST,
    TRAITOR,
    VIGILANTE,
    VILLAGER,
    NightActionKind,
    Team,
)

_ALL_ROLES = (
    VILLAGER,
    MAFIA_ROLE,
    DETECTIVE,
    DOCTOR,
    BODYGUARD,
    VIGILANTE,
    ESCORT,
    GODFATHER,
    MAYOR,
    JESTER,
    SERIAL_KILLER,
    SURVIVOR,
    TERRORIST,
    TRAITOR,
)


def test_registry_contains_all_fourteen_roles():
    assert set(ROLE_REGISTRY.keys()) == {
        "villager",
        "mafia",
        "detective",
        "doctor",
        "bodyguard",
        "vigilante",
        "escort",
        "godfather",
        "mayor",
        "jester",
        "serial_killer",
        "survivor",
        "terrorist",
        "traitor",
    }
    for role in _ALL_ROLES:
        assert ROLE_REGISTRY[role.key] is role


def test_team_membership():
    assert {role.key for role in _ALL_ROLES if role.team == Team.MAFIA} == {"mafia", "godfather", "terrorist"}
    assert {role.key for role in _ALL_ROLES if role.team == Team.NEUTRAL} == {
        "jester",
        "serial_killer",
        "survivor",
        "traitor",
    }
    assert {role.key for role in _ALL_ROLES if role.team == Team.TOWN} == {
        "villager",
        "detective",
        "doctor",
        "bodyguard",
        "vigilante",
        "escort",
        "mayor",
    }


def test_acts_at_night_matches_night_action_kind():
    no_night_action_roles = {"villager", "mayor", "jester", "survivor", "traitor"}
    for role in _ALL_ROLES:
        if role.key in no_night_action_roles:
            assert role.acts_at_night is False
            assert role.night_action_kind == NightActionKind.NONE
        else:
            assert role.acts_at_night is True
            assert role.night_action_kind != NightActionKind.NONE


def test_self_targeting_disallowed_only_for_specific_roles():
    no_self_target_keys = {"mafia", "detective", "vigilante", "escort", "godfather", "serial_killer", "terrorist"}
    for role in _ALL_ROLES:
        expected = role.key not in no_self_target_keys
        assert role.allow_self_target is expected, role.key


def test_only_serial_killer_is_hostile():
    for role in _ALL_ROLES:
        assert role.hostile is (role.key == "serial_killer")


def test_only_vigilante_has_limited_uses():
    for role in _ALL_ROLES:
        if role.key == "vigilante":
            assert role.max_uses == 2
        else:
            assert role.max_uses is None


def test_godfather_investigates_as_town_despite_mafia_team():
    assert GODFATHER.team == Team.MAFIA
    assert GODFATHER.investigate_as == Team.TOWN
    for role in _ALL_ROLES:
        if role.key not in ("godfather", "traitor"):
            assert role.investigate_as is None


def test_traitor_investigates_as_town_despite_neutral_team():
    assert TRAITOR.team == Team.NEUTRAL
    assert TRAITOR.investigate_as == Team.TOWN


def test_mafia_and_godfather_share_the_mafia_kill_night_action():
    assert MAFIA_ROLE.night_action_kind == NightActionKind.MAFIA_KILL
    assert GODFATHER.night_action_kind == NightActionKind.MAFIA_KILL


def test_terrorist_has_its_own_night_action_kind_not_mafia_kill():
    assert TERRORIST.team == Team.MAFIA
    assert TERRORIST.night_action_kind == NightActionKind.TERRORIST_BOMB
    assert TERRORIST.night_action_kind != NightActionKind.MAFIA_KILL
    assert TERRORIST.investigate_as is None
