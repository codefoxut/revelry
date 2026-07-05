from dataclasses import dataclass
from enum import Enum


class Team(str, Enum):
    """Which side a role is on — the basis for step 11's win-check."""

    TOWN = "town"
    MAFIA = "mafia"


@dataclass(frozen=True)
class Role:
    """A Mafia role's identity and metadata. Deliberately data-only: night-
    action resolution, voting, and win-checking are step 11's job and will
    dispatch on `key`/`team`/`acts_at_night` rather than needing behavior
    methods on this class.
    """

    key: str
    display_name: str
    team: Team
    description: str
    acts_at_night: bool = False


VILLAGER = Role(
    key="villager",
    display_name="Villager",
    team=Team.TOWN,
    description="No special ability. Use the day's discussion and your vote to find the mafia.",
)

MAFIA_ROLE = Role(
    key="mafia",
    display_name="Mafia",
    team=Team.MAFIA,
    description="Each night, choose a player alongside the rest of the mafia to eliminate.",
    acts_at_night=True,
)

DETECTIVE = Role(
    key="detective",
    display_name="Detective",
    team=Team.TOWN,
    description="Each night, investigate one player to learn which team they're on.",
    acts_at_night=True,
)

DOCTOR = Role(
    key="doctor",
    display_name="Doctor",
    team=Team.TOWN,
    description="Each night, choose one player to protect from elimination.",
    acts_at_night=True,
)

# Keyed registry so future roles (Jester, Witch, ...) can be added here
# without touching engine or assignment code.
ROLE_REGISTRY: dict[str, Role] = {role.key: role for role in (VILLAGER, MAFIA_ROLE, DETECTIVE, DOCTOR)}
