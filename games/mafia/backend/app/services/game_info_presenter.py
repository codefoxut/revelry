from app.games.mafia.reference_content import FAQ, PHASES, ROLE_EXAMPLES, RULES_SECTIONS, TIE_BREAKERS
from app.games.mafia.role_assignment import MUTUALLY_EXCLUSIVE_ROLE_PAIRS
from app.games.mafia.roles import ROLE_REGISTRY
from app.schemas.game_info import (
    FaqEntryOut,
    GameInfoOut,
    PhaseInfoOut,
    RoleInfoOut,
    RuleSectionOut,
    TieBreakerInfoOut,
    TieBreakerOptionOut,
)


def _mutually_exclusive_with(role_key: str) -> list[str]:
    partners: set[str] = set()
    for pair in MUTUALLY_EXCLUSIVE_ROLE_PAIRS:
        if role_key in pair:
            partners |= pair - {role_key}
    return sorted(partners)


def build_game_info() -> GameInfoOut:
    """Assemble the full reference-data payload from the live role registry
    plus the hand-authored copy in `reference_content.py`, so roles/pairs
    served here can never drift from what `ROLE_REGISTRY` and
    `MUTUALLY_EXCLUSIVE_ROLE_PAIRS` actually enforce during gameplay.
    """
    roles = [
        RoleInfoOut(
            key=role.key,
            display_name=role.display_name,
            team=role.team.value,
            description=role.description,
            example=ROLE_EXAMPLES[role.key],
            acts_at_night=role.acts_at_night,
            allow_self_target=role.allow_self_target,
            hostile=role.hostile,
            max_uses=role.max_uses,
            mutually_exclusive_with=_mutually_exclusive_with(role.key),
        )
        for role in ROLE_REGISTRY.values()
    ]

    phases = [
        PhaseInfoOut(key=phase.key, name=phase.name, summary=phase.summary, details=phase.details, example=phase.example)
        for phase in PHASES
    ]

    tie_breakers = [
        TieBreakerInfoOut(
            key=tie_breaker.key,
            title=tie_breaker.title,
            description=tie_breaker.description,
            options=[
                TieBreakerOptionOut(key=option.key, label=option.label, description=option.description, example=option.example)
                for option in tie_breaker.options
            ],
        )
        for tie_breaker in TIE_BREAKERS
    ]

    rules = [RuleSectionOut(title=section.title, body=section.body, example=section.example) for section in RULES_SECTIONS]

    faq = [FaqEntryOut(question=entry.question, answer=entry.answer) for entry in FAQ]

    return GameInfoOut(roles=roles, phases=phases, tie_breakers=tie_breakers, rules=rules, faq=faq)
