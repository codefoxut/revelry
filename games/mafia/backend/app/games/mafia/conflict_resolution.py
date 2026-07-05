from enum import Enum


class ConflictResolution(str, Enum):
    """What happens on NIGHT resolution if living mafia haven't locked in a
    shared target. Chosen by the host per-game via StartGameCommand.
    """

    KILL_ANY = "kill_any"  # a random living player dies, mafia included
    NO_KILL = "no_kill"  # no one dies
