from __future__ import annotations

from typing import Literal

from app.game_engine.base import Command


class StartGameCommand(Command):
    active_player_ids: list[str]


class SubmitVoteCommand(Command):
    choice: Literal["a", "b"]


class RevealCommand(Command):
    pass


class NextQuestionCommand(Command):
    pass
