import random

from app.games.mafia.roles import MAFIA_ROLE, ROLE_REGISTRY, VILLAGER, Role
from app.platform.exceptions import InvalidGameSettingsError

# Preserves the app's original fixed roster (villager/mafia/detective/doctor)
# for any caller that doesn't pass an explicit selection.
DEFAULT_ENABLED_ROLE_KEYS: frozenset[str] = frozenset({"detective", "doctor"})

# Roles enabled via `enabled_role_keys` that replace a mafia-team slot
# instead of adding an extra one — e.g. Godfather leads the team kill just
# like a plain Mafia member.
_MAFIA_SUB_ROLE_KEYS: frozenset[str] = frozenset({"godfather"})


def clamp_mafia_count(player_count: int, requested: int | None) -> int:
    """Clamp a host-requested mafia count to a sane range: at least 1, and
    never so many that fewer than 2 non-mafia players remain.
    """
    if requested is None:
        return max(1, player_count // 4)
    max_mafia = max(1, min(player_count // 3, player_count - 2))
    return max(1, min(requested, max_mafia))


def build_composition(player_count: int, mafia_count: int, enabled_role_keys: frozenset[str]) -> list[Role]:
    """Assemble the list of roles for a game: `mafia_count` mafia-team
    slots (one becomes Godfather if that key is enabled), one instance of
    each other enabled Town/Neutral special role, and the rest Villager.

    Raises InvalidGameSettingsError rather than silently dropping a role or
    clamping villagers below zero — a hidden-information game must not
    silently omit a role the host explicitly enabled.
    """
    mafia_sub_keys = enabled_role_keys & _MAFIA_SUB_ROLE_KEYS
    special_keys = enabled_role_keys - _MAFIA_SUB_ROLE_KEYS - {"villager", "mafia"}

    mafia_roles: list[Role] = [ROLE_REGISTRY[key] for key in sorted(mafia_sub_keys)]
    mafia_roles.extend([MAFIA_ROLE] * max(0, mafia_count - len(mafia_roles)))

    special_roles = [ROLE_REGISTRY[key] for key in sorted(special_keys)]

    total_special = len(mafia_roles) + len(special_roles)
    if total_special > player_count:
        raise InvalidGameSettingsError(
            f"{total_special} roles enabled for only {player_count} players"
        )

    villager_count = player_count - total_special
    return [*mafia_roles, *special_roles, *([VILLAGER] * villager_count)]


def assign_roles(
    player_ids: list[str],
    rng: random.Random,
    *,
    mafia_count: int | None = None,
    enabled_role_keys: frozenset[str] | set[str] | None = None,
) -> dict[str, Role]:
    """Randomly assign each active player one role from the composition for
    their player count. `rng` is injected so tests can seed it for
    deterministic assignments. `mafia_count`/`enabled_role_keys` default to
    the app's original fixed roster when omitted.
    """
    player_count = len(player_ids)
    resolved_mafia_count = clamp_mafia_count(player_count, mafia_count)
    resolved_role_keys = (
        DEFAULT_ENABLED_ROLE_KEYS if enabled_role_keys is None else frozenset(enabled_role_keys)
    )

    roles = build_composition(player_count, resolved_mafia_count, resolved_role_keys)
    shuffled_ids = list(player_ids)
    rng.shuffle(shuffled_ids)
    return dict(zip(shuffled_ids, roles))
