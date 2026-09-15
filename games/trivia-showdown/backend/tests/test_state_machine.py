import pytest

from app.games.trivia_showdown.phases import TRIVIA_TRANSITIONS, TriviaPhase
from app.platform.state_machine import StateMachine


def test_initial_phase_is_lobby():
    machine = StateMachine(TriviaPhase.LOBBY, TRIVIA_TRANSITIONS)
    assert machine.phase == TriviaPhase.LOBBY


def test_lobby_can_only_open_the_first_question():
    machine = StateMachine(TriviaPhase.LOBBY, TRIVIA_TRANSITIONS)
    assert machine.can_transition_to(TriviaPhase.QUESTION_OPEN)
    assert not machine.can_transition_to(TriviaPhase.ANSWERING)


def test_a_buzz_moves_into_answering_and_back():
    machine = StateMachine(TriviaPhase.LOBBY, TRIVIA_TRANSITIONS)
    machine.transition_to(TriviaPhase.QUESTION_OPEN)
    machine.transition_to(TriviaPhase.ANSWERING)
    machine.transition_to(TriviaPhase.QUESTION_OPEN)
    assert machine.phase == TriviaPhase.QUESTION_OPEN


def test_revealed_can_advance_to_the_next_question_or_end_the_game():
    machine = StateMachine(TriviaPhase.LOBBY, TRIVIA_TRANSITIONS)
    machine.transition_to(TriviaPhase.QUESTION_OPEN)
    machine.transition_to(TriviaPhase.REVEALED)
    assert machine.can_transition_to(TriviaPhase.QUESTION_OPEN)
    assert machine.can_transition_to(TriviaPhase.GAME_OVER)
    machine.transition_to(TriviaPhase.GAME_OVER)
    assert machine.phase == TriviaPhase.GAME_OVER


def test_game_over_is_terminal():
    machine = StateMachine(TriviaPhase.GAME_OVER, TRIVIA_TRANSITIONS)
    assert not machine.can_transition_to(TriviaPhase.QUESTION_OPEN)
    with pytest.raises(ValueError):
        machine.transition_to(TriviaPhase.QUESTION_OPEN)


def test_cannot_skip_lobby_straight_to_answering():
    machine = StateMachine(TriviaPhase.LOBBY, TRIVIA_TRANSITIONS)
    with pytest.raises(ValueError):
        machine.transition_to(TriviaPhase.ANSWERING)
