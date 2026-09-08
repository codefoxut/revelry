import pytest

from app.games.spyfall.phases import SPYFALL_TRANSITIONS, SpyfallPhase
from app.platform.state_machine import StateMachine


def test_initial_phase_is_lobby():
    machine = StateMachine(SpyfallPhase.LOBBY, SPYFALL_TRANSITIONS)
    assert machine.phase == SpyfallPhase.LOBBY


def test_full_cycle_to_game_over_is_legal():
    machine = StateMachine(SpyfallPhase.LOBBY, SPYFALL_TRANSITIONS)
    for phase in (SpyfallPhase.DISCUSSION, SpyfallPhase.VOTING, SpyfallPhase.GAME_OVER):
        machine.transition_to(phase)
    assert machine.phase == SpyfallPhase.GAME_OVER


def test_discussion_can_also_transition_directly_to_game_over():
    machine = StateMachine(SpyfallPhase.LOBBY, SPYFALL_TRANSITIONS)
    machine.transition_to(SpyfallPhase.DISCUSSION)
    machine.transition_to(SpyfallPhase.GAME_OVER)
    assert machine.phase == SpyfallPhase.GAME_OVER


def test_game_over_is_terminal():
    machine = StateMachine(SpyfallPhase.GAME_OVER, SPYFALL_TRANSITIONS)
    assert not machine.can_transition_to(SpyfallPhase.DISCUSSION)
    with pytest.raises(ValueError):
        machine.transition_to(SpyfallPhase.DISCUSSION)


def test_cannot_skip_phases():
    machine = StateMachine(SpyfallPhase.LOBBY, SPYFALL_TRANSITIONS)
    with pytest.raises(ValueError):
        machine.transition_to(SpyfallPhase.VOTING)
