import pytest

from app.games.codenames.phases import CODENAMES_TRANSITIONS, CodenamesPhase
from app.platform.state_machine import StateMachine


def test_initial_phase_is_lobby():
    machine = StateMachine(CodenamesPhase.LOBBY, CODENAMES_TRANSITIONS)
    assert machine.phase == CodenamesPhase.LOBBY


def test_lobby_can_start_on_either_team():
    machine = StateMachine(CodenamesPhase.LOBBY, CODENAMES_TRANSITIONS)
    assert machine.can_transition_to(CodenamesPhase.RED_TURN)
    assert machine.can_transition_to(CodenamesPhase.BLUE_TURN)


def test_turns_alternate_back_and_forth():
    machine = StateMachine(CodenamesPhase.LOBBY, CODENAMES_TRANSITIONS)
    machine.transition_to(CodenamesPhase.RED_TURN)
    machine.transition_to(CodenamesPhase.BLUE_TURN)
    machine.transition_to(CodenamesPhase.RED_TURN)
    assert machine.phase == CodenamesPhase.RED_TURN


def test_either_turn_can_end_the_game():
    machine = StateMachine(CodenamesPhase.LOBBY, CODENAMES_TRANSITIONS)
    machine.transition_to(CodenamesPhase.RED_TURN)
    machine.transition_to(CodenamesPhase.GAME_OVER)
    assert machine.phase == CodenamesPhase.GAME_OVER


def test_game_over_is_terminal():
    machine = StateMachine(CodenamesPhase.GAME_OVER, CODENAMES_TRANSITIONS)
    assert not machine.can_transition_to(CodenamesPhase.RED_TURN)
    with pytest.raises(ValueError):
        machine.transition_to(CodenamesPhase.RED_TURN)


def test_cannot_skip_lobby_straight_to_game_over():
    machine = StateMachine(CodenamesPhase.LOBBY, CODENAMES_TRANSITIONS)
    with pytest.raises(ValueError):
        machine.transition_to(CodenamesPhase.GAME_OVER)
