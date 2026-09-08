from enum import Enum


class DayTieResolution(str, Enum):
    """What happens on VOTING resolution if the plurality vote is tied.
    Chosen by the host per-game via StartGameCommand.
    """

    NO_ELIMINATION = "no_elimination"  # tied votes mean no one is voted out
    RANDOM_AMONG_TIED = "random_among_tied"  # one of the tied players is picked at random
