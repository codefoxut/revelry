from app.game_engine.base import Command
from app.games.mafia.conflict_resolution import ConflictResolution


class StartGameCommand(Command):
    """Move the game from LOBBY into its first NIGHT. Issued once by the
    host; the WS layer is responsible for the host/precondition checks
    before this ever reaches the engine.

    `active_player_ids` is the roster to assign roles to — the engine has
    no knowledge of Room/RoomManager, so GameSessionManager passes it in
    explicitly rather than the engine reaching out to fetch it.
    """

    active_player_ids: list[str]
    conflict_resolution: ConflictResolution = ConflictResolution.KILL_ANY


class AdvancePhaseCommand(Command):
    """Manually advance to the next phase in the cycle. A stand-in for
    automatic timer/vote-driven advancement, which lands in later steps.
    """


class SubmitNightActionCommand(Command):
    """A single player's night action. What it means depends on the
    actor's role: mafia = kill vote, doctor = protect, detective =
    investigate. Only valid during NIGHT, for a living player whose role
    has `acts_at_night`.
    """

    target_player_id: str


class CastVoteCommand(Command):
    """A living player's public vote to eliminate another living player
    during VOTING. Re-voting overwrites the player's previous vote.
    """

    target_player_id: str


class LockNightActionCommand(Command):
    """A mafia player locking in their current night-action target. Only
    valid once that player has already submitted a target via
    SubmitNightActionCommand; changing the target afterward un-locks it.
    """
