from app.game_engine.base import Command


class StartGameCommand(Command):
    """Move the game from LOBBY into DISCUSSION. Issued once by the host;
    the WS layer is responsible for the host/precondition checks before
    this ever reaches the engine.

    `active_player_ids` is the roster to assign a location/spy to — the
    engine has no knowledge of Room/RoomManager, so GameSessionManager
    passes it in explicitly rather than the engine reaching out to fetch
    it. `enabled_location_keys` restricts which locations can be picked
    (None falls back to the full location bank, see locations.py).
    """

    active_player_ids: list[str]
    enabled_location_keys: frozenset[str] | None = None


class AdvancePhaseCommand(Command):
    """Manually advance to the next phase: DISCUSSION -> VOTING, or
    VOTING -> GAME_OVER (resolving the vote). A stand-in for automatic
    timer/vote-driven advancement during DISCUSSION, same as Mafia's.
    """


class CastVoteCommand(Command):
    """A player's public vote for who they think the spy is, cast during
    VOTING. Re-voting overwrites the player's previous vote.
    """

    target_player_id: str


class GuessLocationCommand(Command):
    """The spy's alternate win condition: guessing the secret location.
    Valid at any time during DISCUSSION or VOTING. Resolves the game
    immediately — correct guess wins for the spy, incorrect guess reveals
    them and wins for everyone else.
    """

    location_key: str
