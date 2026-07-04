class RoomNotFoundError(Exception):
    """Raised when a room code doesn't correspond to an active room."""


class RoomFullError(Exception):
    """Raised when joining as a player would exceed the room's capacity."""


class PermissionDeniedError(Exception):
    """Raised when a player attempts an action they aren't authorized for."""
