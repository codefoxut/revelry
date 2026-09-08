import random

import pytest

from app.games.spyfall.commands import (
    AdvancePhaseCommand,
    CastVoteCommand,
    GuessLocationCommand,
    StartGameCommand,
)
from app.games.spyfall.engine import SpyfallGameEngine
from app.games.spyfall.events import GameOverEvent, PhaseChangedEvent, RoleAssignedEvent, VoteCastEvent
from app.games.spyfall.phases import SpyfallPhase
from app.platform.exceptions import InvalidGameStateError

_PLAYER_IDS = ["p1", "p2", "p3", "p4"]


def _new_engine(seed: int = 1) -> SpyfallGameEngine:
    return SpyfallGameEngine("ROOM1", rng=random.Random(seed))


async def _start(engine: SpyfallGameEngine, **kwargs):
    return await engine.handle_command(
        StartGameCommand(player_id=_PLAYER_IDS[0], active_player_ids=_PLAYER_IDS, **kwargs)
    )


def _spy_id(engine: SpyfallGameEngine) -> str:
    return next(pid for pid in _PLAYER_IDS if engine.get_assignment(pid)[0])


@pytest.mark.asyncio
async def test_start_game_transitions_to_discussion_and_assigns_one_spy():
    engine = _new_engine()

    events = await _start(engine)

    assert engine.phase == SpyfallPhase.DISCUSSION
    phase_events = [e for e in events if isinstance(e, PhaseChangedEvent)]
    assert phase_events[0].phase == SpyfallPhase.DISCUSSION
    role_events = [e for e in events if isinstance(e, RoleAssignedEvent)]
    assert len(role_events) == len(_PLAYER_IDS)
    assert sum(1 for e in role_events if e.is_spy) == 1


@pytest.mark.asyncio
async def test_start_game_gives_non_spies_a_location_and_role():
    engine = _new_engine()

    events = await _start(engine)

    for event in events:
        if isinstance(event, RoleAssignedEvent) and not event.is_spy:
            assert event.location is not None
            assert event.role is not None
        elif isinstance(event, RoleAssignedEvent):
            assert event.location is None
            assert event.role is None


@pytest.mark.asyncio
async def test_get_assignment_before_start_raises():
    engine = _new_engine()

    with pytest.raises(InvalidGameStateError):
        engine.get_assignment("p1")


@pytest.mark.asyncio
async def test_advance_phase_from_discussion_moves_to_voting():
    engine = _new_engine()
    await _start(engine)

    events = await engine.handle_command(AdvancePhaseCommand(player_id="p1"))

    assert engine.phase == SpyfallPhase.VOTING
    assert events == [PhaseChangedEvent(phase=SpyfallPhase.VOTING, round_number=1)]


@pytest.mark.asyncio
async def test_advance_phase_before_start_raises():
    engine = _new_engine()

    with pytest.raises(InvalidGameStateError):
        await engine.handle_command(AdvancePhaseCommand(player_id="p1"))


@pytest.mark.asyncio
async def test_cast_vote_during_discussion_raises():
    engine = _new_engine()
    await _start(engine)

    with pytest.raises(InvalidGameStateError):
        await engine.handle_command(CastVoteCommand(player_id="p1", target_player_id="p2"))


@pytest.mark.asyncio
async def test_cast_vote_for_unknown_target_raises():
    engine = _new_engine()
    await _start(engine)
    await engine.handle_command(AdvancePhaseCommand(player_id="p1"))

    with pytest.raises(InvalidGameStateError):
        await engine.handle_command(CastVoteCommand(player_id="p1", target_player_id="ghost"))


@pytest.mark.asyncio
async def test_cast_vote_during_voting_returns_vote_cast_event():
    engine = _new_engine()
    await _start(engine)
    await engine.handle_command(AdvancePhaseCommand(player_id="p1"))

    events = await engine.handle_command(CastVoteCommand(player_id="p1", target_player_id="p2"))

    assert events == [VoteCastEvent(player_id="p1", target_player_id="p2")]


@pytest.mark.asyncio
async def test_resolve_voting_with_a_clear_plurality_accuses_that_player():
    engine = _new_engine()
    await _start(engine)
    await engine.handle_command(AdvancePhaseCommand(player_id="p1"))
    spy_id = _spy_id(engine)
    voters = [pid for pid in _PLAYER_IDS if pid != spy_id]
    for voter_id in voters:
        await engine.handle_command(CastVoteCommand(player_id=voter_id, target_player_id=spy_id))

    events = await engine.handle_command(AdvancePhaseCommand(player_id="p1"))

    assert engine.phase == SpyfallPhase.GAME_OVER
    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_side == "non_spies"
    assert game_over.accused_player_id == spy_id
    assert game_over.spy_player_ids == [spy_id]
    reveal_by_player = {r.player_id: r for r in game_over.reveals}
    assert reveal_by_player[spy_id].is_spy is True
    assert reveal_by_player[spy_id].role is None


@pytest.mark.asyncio
async def test_resolve_voting_with_a_tie_results_in_the_spy_evading():
    engine = _new_engine()
    await _start(engine)
    await engine.handle_command(AdvancePhaseCommand(player_id="p1"))
    await engine.handle_command(CastVoteCommand(player_id=_PLAYER_IDS[0], target_player_id=_PLAYER_IDS[1]))
    await engine.handle_command(CastVoteCommand(player_id=_PLAYER_IDS[2], target_player_id=_PLAYER_IDS[3]))

    events = await engine.handle_command(AdvancePhaseCommand(player_id="p1"))

    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_side == "spies"
    assert game_over.accused_player_id is None


@pytest.mark.asyncio
async def test_resolve_voting_with_no_votes_results_in_the_spy_evading():
    engine = _new_engine()
    await _start(engine)
    await engine.handle_command(AdvancePhaseCommand(player_id="p1"))

    events = await engine.handle_command(AdvancePhaseCommand(player_id="p1"))

    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_side == "spies"
    assert game_over.accused_player_id is None


@pytest.mark.asyncio
async def test_guess_location_correctly_wins_for_the_spy():
    engine = _new_engine()
    await _start(engine, enabled_location_keys=frozenset({"airplane"}))
    spy_id = _spy_id(engine)

    events = await engine.handle_command(GuessLocationCommand(player_id=spy_id, location_key="airplane"))

    assert engine.phase == SpyfallPhase.GAME_OVER
    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_side == "spies"
    assert game_over.accused_player_id is None


@pytest.mark.asyncio
async def test_guess_location_incorrectly_wins_for_non_spies():
    engine = _new_engine()
    await _start(engine, enabled_location_keys=frozenset({"airplane"}))
    spy_id = _spy_id(engine)

    events = await engine.handle_command(GuessLocationCommand(player_id=spy_id, location_key="bank"))

    game_over = next(e for e in events if isinstance(e, GameOverEvent))
    assert game_over.winning_side == "non_spies"
    assert game_over.accused_player_id is None


@pytest.mark.asyncio
async def test_guess_location_by_a_non_spy_raises():
    engine = _new_engine()
    await _start(engine, enabled_location_keys=frozenset({"airplane"}))
    spy_id = _spy_id(engine)
    non_spy_id = next(pid for pid in _PLAYER_IDS if pid != spy_id)

    with pytest.raises(InvalidGameStateError):
        await engine.handle_command(GuessLocationCommand(player_id=non_spy_id, location_key="airplane"))


@pytest.mark.asyncio
async def test_guess_location_with_an_unknown_key_raises():
    engine = _new_engine()
    await _start(engine)
    spy_id = _spy_id(engine)

    with pytest.raises(InvalidGameStateError):
        await engine.handle_command(GuessLocationCommand(player_id=spy_id, location_key="mars_base"))


@pytest.mark.asyncio
async def test_guess_location_after_game_over_raises():
    engine = _new_engine()
    await _start(engine, enabled_location_keys=frozenset({"airplane"}))
    spy_id = _spy_id(engine)
    await engine.handle_command(GuessLocationCommand(player_id=spy_id, location_key="airplane"))

    with pytest.raises(InvalidGameStateError):
        await engine.handle_command(GuessLocationCommand(player_id=spy_id, location_key="airplane"))


@pytest.mark.asyncio
async def test_handle_command_rejects_an_unsupported_command_type():
    engine = _new_engine()

    class BogusCommand:
        pass

    with pytest.raises(InvalidGameStateError):
        await engine.handle_command(BogusCommand())
