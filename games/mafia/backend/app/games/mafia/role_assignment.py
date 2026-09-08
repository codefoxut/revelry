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

# Role pairs that can never both be enabled at once. Escort/Hypnotizer is a
# hard correctness requirement (they share NightActionKind.ESCORT_BLOCK, and
# engine.py's _actor_id_for_kind assumes at most one living instance per
# kind). Detective/Oracle is enforced for the same "exactly one investigator
# role" reason even though they don't share a kind.
MUTUALLY_EXCLUSIVE_ROLE_PAIRS: tuple[frozenset[str], ...] = (
    frozenset({"detective", "oracle"}),
    frozenset({"escort", "hypnotizer"}),
)


# player_count -> (min_mafia, max_mafia, default_mafia), curated for good
# gameplay across the room's 4-20 player range (app/platform/room_manager.py).
# Mirrors MAFIA_COUNT_TABLE in frontend/lib/roles.ts -- both sides must agree
# so the lobby's dropdown bounds always match what the server will accept.
MAFIA_COUNT_TABLE: dict[int, tuple[int, int, int]] = {
    4: (1, 1, 1), 5: (1, 1, 1), 6: (1, 2, 1), 7: (1, 2, 1),
    8: (1, 2, 2), 9: (1, 3, 2), 10: (1, 3, 2), 11: (1, 3, 2),
    12: (1, 4, 3), 13: (1, 4, 3), 14: (1, 4, 3), 15: (1, 5, 3),
    16: (1, 5, 4), 17: (1, 5, 4), 18: (1, 6, 4), 19: (1, 6, 4),
    20: (1, 6, 5),
}


def mafia_count_bounds(player_count: int) -> tuple[int, int, int]:
    """Returns (min, max, default) mafia count for a player count, clamped
    into the table's declared 4-20 range."""
    return MAFIA_COUNT_TABLE[min(max(player_count, 4), 20)]


def clamp_mafia_count(player_count: int, requested: int | None) -> int:
    """Clamp a host-requested mafia count to the good-gameplay table's
    range for this player count.
    """
    min_mafia, max_mafia, default_mafia = mafia_count_bounds(player_count)
    if requested is None:
        return default_mafia
    return max(min_mafia, min(requested, max_mafia))


def build_composition(player_count: int, mafia_count: int, enabled_role_keys: frozenset[str]) -> list[Role]:
    """Assemble the list of roles for a game: `mafia_count` mafia-team
    slots (one becomes Godfather if that key is enabled), one instance of
    each other enabled Town/Neutral special role, and the rest Villager.

    Raises InvalidGameSettingsError rather than silently dropping a role or
    clamping villagers below zero — a hidden-information game must not
    silently omit a role the host explicitly enabled.
    """
    for pair in MUTUALLY_EXCLUSIVE_ROLE_PAIRS:
        if pair <= enabled_role_keys:
            a, b = sorted(pair)
            raise InvalidGameSettingsError(f"{a} and {b} cannot both be enabled in the same game")

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
