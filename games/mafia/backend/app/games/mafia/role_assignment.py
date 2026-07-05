import random

from app.games.mafia.roles import DETECTIVE, DOCTOR, MAFIA_ROLE, Role, VILLAGER


def _role_composition(player_count: int) -> list[Role]:
    """Classic ratio: ~1 mafia per 4 players (min 1), one detective, one
    doctor if there's room, the rest villagers.
    """
    mafia_count = max(1, player_count // 4)
    roles = [MAFIA_ROLE] * mafia_count
    remaining = player_count - mafia_count

    if remaining >= 1:
        roles.append(DETECTIVE)
        remaining -= 1
    if remaining >= 1:
        roles.append(DOCTOR)
        remaining -= 1

    roles.extend([VILLAGER] * remaining)
    return roles


def assign_roles(player_ids: list[str], rng: random.Random) -> dict[str, Role]:
    """Randomly assign each active player one role from the composition for
    their player count. `rng` is injected so tests can seed it for
    deterministic assignments.
    """
    roles = _role_composition(len(player_ids))
    shuffled_ids = list(player_ids)
    rng.shuffle(shuffled_ids)
    return dict(zip(shuffled_ids, roles))
