from __future__ import annotations

from typing import Literal

from app.game_engine.base import Command


class StartGameCommand(Command):
    team_of: dict[str, Literal["a", "b"]]


class BuzzInCommand(Command):
    pass


class RevealSlotCommand(Command):
    slot_index: int


class StrikeCommand(Command):
    pass


class StealRevealCommand(Command):
    slot_index: int


class StealMissCommand(Command):
    pass


class NextRoundCommand(Command):
    pass
