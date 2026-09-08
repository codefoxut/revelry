from __future__ import annotations

import random

from app.game_engine.base import Command, Event, GameEngine
from app.games.codenames.board import BOARD_SIZE, Card, CardColor, Role, Team, build_board, other_team
from app.games.codenames.commands import EndTurnCommand, GiveClueCommand, MakeGuessCommand, StartGameCommand
from app.games.codenames.events import CardRevealedEvent, ClueGivenEvent, GameOverEvent, TeamAssignedEvent
from app.games.codenames.phases import CODENAMES_TRANSITIONS, CodenamesPhase
from app.games.codenames.wordbank import WORD_BANK
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError
from app.platform.state_machine import StateMachine

_MIN_CLUE_NUMBER = 0
_MAX_CLUE_NUMBER = 9


class CodenamesGameEngine(GameEngine):
    """Pure game-rules for one Codenames round. Turn order alternates between
    RED_TURN/BLUE_TURN (unlike Mafia/Spyfall's linear phase progression)
    until a team wins by finding all their words or someone hits the
    assassin card.
    """

    def __init__(self, room_code: str) -> None:
        self._room_code = room_code
        self._state_machine = StateMachine(CodenamesPhase.LOBBY, CODENAMES_TRANSITIONS)
        self._board: list[Card] = []
        self._teams: dict[str, Team] = {}
        self._roles: dict[str, Role] = {}
        self._current_clue: dict[str, object] | None = None
        self._turn_number = 0

    async def handle_command(self, command: Command) -> list[Event]:
        if isinstance(command, StartGameCommand):
            return self._start_game(command)
        if isinstance(command, GiveClueCommand):
            return self._give_clue(command)
        if isinstance(command, MakeGuessCommand):
            return self._make_guess(command)
        if isinstance(command, EndTurnCommand):
            return self._end_turn(command)
        raise ValueError(f"Unhandled command: {command!r}")

    def _start_game(self, command: StartGameCommand) -> list[Event]:
        player_ids = list(command.active_player_ids)
        random.shuffle(player_ids)
        half = len(player_ids) // 2
        red_ids, blue_ids = player_ids[:half], player_ids[half:]

        self._teams = {}
        self._roles = {}
        for team_ids, team in ((red_ids, Team.RED), (blue_ids, Team.BLUE)):
            spymaster_id = random.choice(team_ids)
            for player_id in team_ids:
                self._teams[player_id] = team
                self._roles[player_id] = Role.SPYMASTER if player_id == spymaster_id else Role.GUESSER

        starting_team = random.choice([Team.RED, Team.BLUE])
        words = random.sample(list(WORD_BANK), BOARD_SIZE)
        self._board = build_board(words, starting_team)
        self._current_clue = None
        self._turn_number = 1
        self._state_machine.transition_to(
            CodenamesPhase.RED_TURN if starting_team == Team.RED else CodenamesPhase.BLUE_TURN
        )

        return [
            TeamAssignedEvent(player_id=player_id, team=self._teams[player_id], role=self._roles[player_id])
            for player_id in player_ids
        ]

    def _give_clue(self, command: GiveClueCommand) -> list[Event]:
        team = self._require_current_team()
        if self._roles.get(command.player_id) != Role.SPYMASTER or self._teams.get(command.player_id) != team:
            raise PermissionDeniedError("Only the active team's spymaster can give a clue")
        if self._current_clue is not None:
            raise InvalidGameStateError("A clue has already been given this turn")
        word = command.word.strip()
        if not word:
            raise InvalidGameStateError("Clue word can't be empty")
        if not (_MIN_CLUE_NUMBER <= command.number <= _MAX_CLUE_NUMBER):
            raise InvalidGameStateError(f"Clue number must be between {_MIN_CLUE_NUMBER} and {_MAX_CLUE_NUMBER}")

        max_guesses = 1 if command.number == 0 else command.number + 1
        self._current_clue = {"word": word, "number": command.number, "guesses_made": 0, "max_guesses": max_guesses}
        return [ClueGivenEvent(team=team, word=word, number=command.number)]

    def _make_guess(self, command: MakeGuessCommand) -> list[Event]:
        team = self._require_current_team()
        if self._teams.get(command.player_id) != team:
            raise PermissionDeniedError("Only a member of the active team can guess")
        if self._roles.get(command.player_id) == Role.SPYMASTER:
            raise PermissionDeniedError("The spymaster doesn't make guesses")
        if self._current_clue is None:
            raise InvalidGameStateError("Wait for a clue before guessing")
        if not (0 <= command.card_index < len(self._board)):
            raise InvalidGameStateError("card_index out of range")

        card = self._board[command.card_index]
        if card.revealed:
            raise InvalidGameStateError("That card has already been revealed")

        card.revealed = True
        events: list[Event] = [
            CardRevealedEvent(
                card_index=command.card_index, word=card.word, color=card.color, guessed_by=command.player_id
            )
        ]

        if card.color == CardColor.ASSASSIN:
            events.append(self._finish_game(other_team(team), "assassin"))
            return events

        win_event = self._check_word_win()
        if win_event is not None:
            events.append(win_event)
            return events

        if card.color.value == team.value:
            guesses_made = int(self._current_clue["guesses_made"]) + 1
            self._current_clue["guesses_made"] = guesses_made
            if guesses_made >= int(self._current_clue["max_guesses"]):
                self._switch_turn(team)
        else:
            self._switch_turn(team)

        return events

    def _end_turn(self, command: EndTurnCommand) -> list[Event]:
        team = self._require_current_team()
        if self._teams.get(command.player_id) != team:
            raise PermissionDeniedError("Only a member of the active team can end the turn")
        if self._roles.get(command.player_id) == Role.SPYMASTER:
            raise PermissionDeniedError("The spymaster doesn't end the team's turn")
        self._switch_turn(team)
        return []

    def _require_current_team(self) -> Team:
        phase = self._state_machine.phase
        if phase == CodenamesPhase.RED_TURN:
            return Team.RED
        if phase == CodenamesPhase.BLUE_TURN:
            return Team.BLUE
        raise InvalidGameStateError("No active team turn right now")

    def _check_word_win(self) -> Event | None:
        red_remaining = sum(1 for card in self._board if card.color == CardColor.RED and not card.revealed)
        blue_remaining = sum(1 for card in self._board if card.color == CardColor.BLUE and not card.revealed)
        if red_remaining == 0:
            return self._finish_game(Team.RED, "all_words_found")
        if blue_remaining == 0:
            return self._finish_game(Team.BLUE, "all_words_found")
        return None

    def _finish_game(self, winner: Team, reason: str) -> Event:
        self._state_machine.transition_to(CodenamesPhase.GAME_OVER)
        for card in self._board:
            card.revealed = True
        self._current_clue = None
        return GameOverEvent(winning_side=winner, reason=reason, colors=[card.color for card in self._board])

    def _switch_turn(self, current_team: Team) -> None:
        next_team = other_team(current_team)
        self._state_machine.transition_to(
            CodenamesPhase.RED_TURN if next_team == Team.RED else CodenamesPhase.BLUE_TURN
        )
        self._current_clue = None
        self._turn_number += 1

    def phase_snapshot(self) -> dict[str, object]:
        current_team: str | None = None
        if self._state_machine.phase == CodenamesPhase.RED_TURN:
            current_team = Team.RED.value
        elif self._state_machine.phase == CodenamesPhase.BLUE_TURN:
            current_team = Team.BLUE.value

        board = [
            {
                "word": card.word,
                "revealed": card.revealed,
                "color": card.color.value if card.revealed else None,
            }
            for card in self._board
        ]
        red_remaining = sum(1 for card in self._board if card.color == CardColor.RED and not card.revealed)
        blue_remaining = sum(1 for card in self._board if card.color == CardColor.BLUE and not card.revealed)

        return {
            "phase": self._state_machine.phase.value,
            "round_number": self._turn_number,
            "current_team": current_team,
            "current_clue": dict(self._current_clue) if self._current_clue is not None else None,
            "board": board,
            "red_remaining": red_remaining,
            "blue_remaining": blue_remaining,
        }

    def get_team_assignment(self, player_id: str) -> tuple[Team, Role] | None:
        team = self._teams.get(player_id)
        role = self._roles.get(player_id)
        if team is None or role is None:
            return None
        return team, role

    def get_spymaster_colors(self, player_id: str) -> list[str] | None:
        """Pragmatic Codenames-specific accessor, mirroring Spyfall's
        `get_assignment()`: the full board's colors are the one piece of
        state that's genuinely per-role rather than per-phase, so it lives
        here rather than in the generic GameEngine interface.
        """
        if self._roles.get(player_id) != Role.SPYMASTER:
            return None
        return [card.color.value for card in self._board]
