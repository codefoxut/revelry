from __future__ import annotations

from app.game_engine.base import Command


class StartGameCommand(Command):
    active_player_ids: list[str]


class GiveClueCommand(Command):
    word: str
    number: int


class MakeGuessCommand(Command):
    card_index: int


class EndTurnCommand(Command):
    pass
