from app.game_engine.base import Command


class StartGameCommand(Command):
    """Move the game from LOBBY into its first NIGHT. Issued once by the
    host; the WS layer is responsible for the host/precondition checks
    before this ever reaches the engine.
    """


class AdvancePhaseCommand(Command):
    """Manually advance to the next phase in the cycle. A stand-in for
    automatic timer/vote-driven advancement, which lands in later steps.
    """
