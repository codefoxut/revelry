from app.games.mafia.conflict_resolution import ConflictResolution
from app.games.mafia.day_tie_resolution import DayTieResolution
from app.games.mafia.reference_content import FAQ, PHASES, ROLE_EXAMPLES, RULES_SECTIONS, TIE_BREAKERS
from app.games.mafia.roles import ROLE_REGISTRY


def test_every_role_has_a_worked_example():
    assert set(ROLE_EXAMPLES.keys()) == set(ROLE_REGISTRY.keys())
    for example in ROLE_EXAMPLES.values():
        assert example.strip()


def test_phases_cover_the_four_round_phases():
    assert [phase.key for phase in PHASES] == ["night", "day", "voting", "elimination"]
    for phase in PHASES:
        assert phase.summary.strip()
        assert phase.details.strip()
        assert phase.example.strip()


def test_tie_breakers_fully_cover_both_settings_enums():
    by_key = {tie_breaker.key: tie_breaker for tie_breaker in TIE_BREAKERS}
    assert set(by_key.keys()) == {"conflict_resolution", "day_tie_resolution"}

    conflict_option_keys = {option.key for option in by_key["conflict_resolution"].options}
    assert conflict_option_keys == {member.value for member in ConflictResolution}

    day_tie_option_keys = {option.key for option in by_key["day_tie_resolution"].options}
    assert day_tie_option_keys == {member.value for member in DayTieResolution}


def test_rules_sections_are_non_empty():
    assert len(RULES_SECTIONS) > 0
    for section in RULES_SECTIONS:
        assert section.title.strip()
        assert section.body.strip()


def test_faq_is_non_empty():
    assert len(FAQ) > 0
    for entry in FAQ:
        assert entry.question.strip()
        assert entry.answer.strip()
