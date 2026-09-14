from __future__ import annotations

from app.game_engine.base import Command


class StartGameCommand(Command):
    active_player_ids: list[str]


class SubmitAnswerCommand(Command):
    text: str


class RevealCommand(Command):
    pass


class StartVoteCommand(Command):
    pass


class CastVoteCommand(Command):
    submission_id: str


class NextPromptCommand(Command):
    pass
