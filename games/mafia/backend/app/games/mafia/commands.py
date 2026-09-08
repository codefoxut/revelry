from app.game_engine.base import Command
from app.games.mafia.conflict_resolution import ConflictResolution
from app.games.mafia.day_tie_resolution import DayTieResolution


class StartGameCommand(Command):
    """Move the game from LOBBY into its first NIGHT. Issued once by the
    host; the WS layer is responsible for the host/precondition checks
    before this ever reaches the engine.

    `active_player_ids` is the roster to assign roles to — the engine has
    no knowledge of Room/RoomManager, so GameSessionManager passes it in
    explicitly rather than the engine reaching out to fetch it.

    `mafia_count`/`enabled_role_keys` configure the role composition (None
    falls back to the app's original fixed roster, see role_assignment.py).
    """

    active_player_ids: list[str]
    conflict_resolution: ConflictResolution = ConflictResolution.KILL_ANY
    day_tie_resolution: DayTieResolution = DayTieResolution.NO_ELIMINATION
    mafia_count: int | None = None
    enabled_role_keys: frozenset[str] | None = None


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


class RevealMayorCommand(Command):
    """The Mayor publicly revealing to permanently double their vote
    weight. Only valid for the Mayor, during DAY or VOTING. Idempotent — a
    second reveal is a no-op rather than an error.
    """


class WithdrawBombCommand(Command):
    """The Terrorist withdrawing their currently-armed bomb before it
    detonates. Only valid for the Terrorist, during NIGHT, while a bomb is
    pending — there's nothing to withdraw otherwise.
    """
