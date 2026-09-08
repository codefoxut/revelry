from __future__ import annotations

import random

from app.games.spyfall.locations import LOCATION_REGISTRY
from app.platform.exceptions import InvalidGameSettingsError


def assign_roles(
    active_player_ids: list[str],
    rng: random.Random,
    enabled_location_keys: frozenset[str] | None = None,
) -> tuple[str, dict[str, str | None]]:
    """Pick a random location (from `enabled_location_keys`, or the full
    registry when omitted) and a random spy, then deal every other player a
    role drawn from that location's role list.

    Returns `(location_key, roles_by_player)`, where `roles_by_player[pid]`
    is `None` exactly for the spy — the sentinel doubles as "who's the spy"
    so callers never need a second lookup.

    Locations don't have a fixed slot count the way Mafia's roles do (see
    role_assignment.py's InvalidGameSettingsError-on-overflow check) — a
    location's role list simply cycles if there are more non-spy players
    than distinct roles, since the role name is flavor text, not a game
    mechanic.
    """
    candidate_keys = list(enabled_location_keys) if enabled_location_keys is not None else list(LOCATION_REGISTRY)
    if not candidate_keys:
        raise InvalidGameSettingsError("At least one location must be enabled")
    unknown_keys = set(candidate_keys) - set(LOCATION_REGISTRY)
    if unknown_keys:
        raise InvalidGameSettingsError(f"Unknown location key(s): {sorted(unknown_keys)}")

    location_key = rng.choice(candidate_keys)
    location = LOCATION_REGISTRY[location_key]

    spy_id = rng.choice(active_player_ids)
    non_spy_ids = [player_id for player_id in active_player_ids if player_id != spy_id]

    roles_pool = list(location.roles)
    rng.shuffle(roles_pool)

    roles_by_player: dict[str, str | None] = {
        player_id: roles_pool[index % len(roles_pool)] for index, player_id in enumerate(non_spy_ids)
    }
    roles_by_player[spy_id] = None
    return location_key, roles_by_player
