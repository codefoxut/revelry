from __future__ import annotations

from app.game_engine.base import Command


class StartGameCommand(Command):
    active_player_ids: list[str]


class BuzzInCommand(Command):
    pass


class JudgeAnswerCommand(Command):
    correct: bool


class RevealCommand(Command):
    pass


class NextQuestionCommand(Command):
    pass
