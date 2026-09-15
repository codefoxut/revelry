from __future__ import annotations

from app.game_engine.base import Command


class StartGameCommand(Command):
    active_player_ids: list[str]


class SubmitStatementsCommand(Command):
    statements: list[str]
    lie_index: int


class CastVoteCommand(Command):
    choice_index: int


class RevealCommand(Command):
    pass


class NextRoundCommand(Command):
    pass
