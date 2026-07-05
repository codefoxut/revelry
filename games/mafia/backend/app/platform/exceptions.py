class RoomNotFoundError(Exception):
    """Raised when a room code doesn't correspond to an active room."""


class RoomFullError(Exception):
    """Raised when joining as a player would exceed the room's capacity."""


class PermissionDeniedError(Exception):
    """Raised when a player attempts an action they aren't authorized for."""


class PlayerNotFoundError(Exception):
    """Raised when a player id doesn't correspond to a player in the room."""


class NotEnoughPlayersError(Exception):
    """Raised when starting a game with fewer active players than the
    game module requires.
    """


class GameAlreadyStartedError(Exception):
    """Raised when starting a game for a room that isn't in the lobby."""


class GameNotStartedError(Exception):
    """Raised when acting on a game (e.g. advancing its phase) before it
    has been started.
    """


class InvalidGameStateError(Exception):
    """Raised when a game action is illegal in the engine's current phase
    (e.g. advancing past a terminal phase).
    """
