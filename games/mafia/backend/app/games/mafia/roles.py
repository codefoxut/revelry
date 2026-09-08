from dataclasses import dataclass
from enum import Enum


class Team(str, Enum):
    """Which side a role is on — the basis for the win-check."""

    TOWN = "town"
    MAFIA = "mafia"
    NEUTRAL = "neutral"


class NightActionKind(str, Enum):
    """What a role's night action actually does. `_submit_night_action`
    dispatches on this instead of `role.key`, so a new role (e.g. Godfather)
    can share Mafia's kill/lock mechanics purely by sharing this value,
    without any role-key special-casing.
    """

    NONE = "none"
    MAFIA_KILL = "mafia_kill"
    DOCTOR_PROTECT = "doctor_protect"
    DETECTIVE_INVESTIGATE = "detective_investigate"
    BODYGUARD_PROTECT = "bodyguard_protect"
    VIGILANTE_KILL = "vigilante_kill"
    ESCORT_BLOCK = "escort_block"
    SERIAL_KILLER_KILL = "serial_killer_kill"
    TERRORIST_BOMB = "terrorist_bomb"


@dataclass(frozen=True)
class Role:
    """A Mafia role's identity and metadata. Deliberately data-only: night-
    action resolution, voting, and win-checking dispatch on
    `night_action_kind`/`team`/`acts_at_night` rather than needing behavior
    methods on this class.
    """

    key: str
    display_name: str
    team: Team
    description: str
    acts_at_night: bool = False
    night_action_kind: NightActionKind = NightActionKind.NONE
    allow_self_target: bool = True
    hostile: bool = False
    max_uses: int | None = None
    # Godfather: investigates as Town despite being on the Mafia team. None
    # means "use `team` as-is".
    investigate_as: Team | None = None


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
    night_action_kind=NightActionKind.MAFIA_KILL,
    allow_self_target=False,
)

DETECTIVE = Role(
    key="detective",
    display_name="Detective",
    team=Team.TOWN,
    description="Each night, investigate one player to learn which team they're on.",
    acts_at_night=True,
    night_action_kind=NightActionKind.DETECTIVE_INVESTIGATE,
    allow_self_target=False,
)

DOCTOR = Role(
    key="doctor",
    display_name="Doctor",
    team=Team.TOWN,
    description="Each night, choose one player to protect from elimination.",
    acts_at_night=True,
    night_action_kind=NightActionKind.DOCTOR_PROTECT,
)

BODYGUARD = Role(
    key="bodyguard",
    display_name="Bodyguard",
    team=Team.TOWN,
    description=(
        "Each night, choose one player to guard. If the mafia targets your "
        "guarded player, you die defending them instead."
    ),
    acts_at_night=True,
    night_action_kind=NightActionKind.BODYGUARD_PROTECT,
)

VIGILANTE = Role(
    key="vigilante",
    display_name="Vigilante",
    team=Team.TOWN,
    description=(
        "Each night, you may kill one player. You only have 2 shots for the "
        "whole game — use them wisely."
    ),
    acts_at_night=True,
    night_action_kind=NightActionKind.VIGILANTE_KILL,
    allow_self_target=False,
    max_uses=2,
)

ESCORT = Role(
    key="escort",
    display_name="Escort",
    team=Team.TOWN,
    description="Each night, choose one player to distract — blocking whatever night action they attempt.",
    acts_at_night=True,
    night_action_kind=NightActionKind.ESCORT_BLOCK,
    allow_self_target=False,
)

GODFATHER = Role(
    key="godfather",
    display_name="Godfather",
    team=Team.MAFIA,
    description=(
        "Leads the mafia's nightly kill just like any mafia member, but "
        "appears innocent to a detective's investigation."
    ),
    acts_at_night=True,
    night_action_kind=NightActionKind.MAFIA_KILL,
    allow_self_target=False,
    investigate_as=Team.TOWN,
)

MAYOR = Role(
    key="mayor",
    display_name="Mayor",
    team=Team.TOWN,
    description="Has no night action. May publicly reveal at any time during the day to permanently double the weight of their vote.",
)

JESTER = Role(
    key="jester",
    display_name="Jester",
    team=Team.NEUTRAL,
    description="Wins alone if the town votes to lynch you. A night kill doesn't count.",
)

SERIAL_KILLER = Role(
    key="serial_killer",
    display_name="Serial Killer",
    team=Team.NEUTRAL,
    description="Each night, kill a player independent of the mafia. Wins alone by being the last one standing.",
    acts_at_night=True,
    night_action_kind=NightActionKind.SERIAL_KILLER_KILL,
    allow_self_target=False,
    hostile=True,
)

SURVIVOR = Role(
    key="survivor",
    display_name="Survivor",
    team=Team.NEUTRAL,
    description="Has no night action. Wins personally simply by surviving to the end of the game, alive.",
)

TERRORIST = Role(
    key="terrorist",
    display_name="Terrorist",
    team=Team.MAFIA,
    description=(
        "Each night, plant a bomb on a player. It doesn't go off that night — it detonates during the "
        "following night's resolution unless you withdraw it first. Counts toward the mafia's win, but "
        "doesn't know who the mafia are and never sees their picks."
    ),
    acts_at_night=True,
    night_action_kind=NightActionKind.TERRORIST_BOMB,
    allow_self_target=False,
)

TRAITOR = Role(
    key="traitor",
    display_name="Traitor",
    team=Team.NEUTRAL,
    description=(
        "Has no night action and looks like an ordinary villager, even to a detective's investigation. "
        "Secretly wins alongside the mafia."
    ),
    investigate_as=Team.TOWN,
)

# Keyed registry so the host's enabled-role selection can look roles up by
# key, and `build_composition` can assemble a game's roster from it.
ROLE_REGISTRY: dict[str, Role] = {
    role.key: role
    for role in (
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
}
