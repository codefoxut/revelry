import pytest

from app.games.mafia.phases import MAFIA_TRANSITIONS, MafiaPhase
from app.platform.state_machine import StateMachine


def test_initial_phase_is_lobby():
    machine = StateMachine(MafiaPhase.LOBBY, MAFIA_TRANSITIONS)
    assert machine.phase == MafiaPhase.LOBBY


def test_full_cycle_back_to_night_is_legal():
    machine = StateMachine(MafiaPhase.LOBBY, MAFIA_TRANSITIONS)
    for phase in (MafiaPhase.NIGHT, MafiaPhase.DAY, MafiaPhase.VOTING, MafiaPhase.ELIMINATION, MafiaPhase.NIGHT):
        machine.transition_to(phase)
    assert machine.phase == MafiaPhase.NIGHT


def test_elimination_can_also_transition_to_game_over():
    machine = StateMachine(MafiaPhase.LOBBY, MAFIA_TRANSITIONS)
    for phase in (MafiaPhase.NIGHT, MafiaPhase.DAY, MafiaPhase.VOTING, MafiaPhase.ELIMINATION, MafiaPhase.GAME_OVER):
        machine.transition_to(phase)
    assert machine.phase == MafiaPhase.GAME_OVER


def test_game_over_is_terminal():
    machine = StateMachine(MafiaPhase.GAME_OVER, MAFIA_TRANSITIONS)
    assert not machine.can_transition_to(MafiaPhase.NIGHT)
    with pytest.raises(ValueError):
        machine.transition_to(MafiaPhase.NIGHT)


def test_cannot_skip_phases():
    machine = StateMachine(MafiaPhase.LOBBY, MAFIA_TRANSITIONS)
    with pytest.raises(ValueError):
        machine.transition_to(MafiaPhase.VOTING)
