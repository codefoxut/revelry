import pytest

from app.games.would_you_rather.phases import WOULD_YOU_RATHER_TRANSITIONS, Phase
from app.platform.state_machine import StateMachine


def test_initial_phase_is_lobby():
    machine = StateMachine(Phase.LOBBY, WOULD_YOU_RATHER_TRANSITIONS)
    assert machine.phase == Phase.LOBBY


def test_lobby_can_only_open_the_first_question():
    machine = StateMachine(Phase.LOBBY, WOULD_YOU_RATHER_TRANSITIONS)
    assert machine.can_transition_to(Phase.QUESTION_OPEN)
    assert not machine.can_transition_to(Phase.REVEALED)


def test_question_open_transitions_to_revealed():
    machine = StateMachine(Phase.LOBBY, WOULD_YOU_RATHER_TRANSITIONS)
    machine.transition_to(Phase.QUESTION_OPEN)
    machine.transition_to(Phase.REVEALED)
    assert machine.phase == Phase.REVEALED


def test_revealed_can_advance_to_next_question_or_game_over():
    machine = StateMachine(Phase.LOBBY, WOULD_YOU_RATHER_TRANSITIONS)
    machine.transition_to(Phase.QUESTION_OPEN)
    machine.transition_to(Phase.REVEALED)
    assert machine.can_transition_to(Phase.QUESTION_OPEN)
    assert machine.can_transition_to(Phase.GAME_OVER)
    machine.transition_to(Phase.GAME_OVER)
    assert machine.phase == Phase.GAME_OVER


def test_game_over_is_terminal():
    machine = StateMachine(Phase.GAME_OVER, WOULD_YOU_RATHER_TRANSITIONS)
    assert not machine.can_transition_to(Phase.QUESTION_OPEN)
    with pytest.raises(ValueError):
        machine.transition_to(Phase.QUESTION_OPEN)
