import pytest

from app.games.codenames.board import CardColor, Role, Team
from app.games.codenames.commands import EndTurnCommand, GiveClueCommand, MakeGuessCommand, StartGameCommand
from app.games.codenames.engine import CodenamesGameEngine
from app.games.codenames.events import CardRevealedEvent, ClueGivenEvent, GameOverEvent, TeamAssignedEvent
from app.games.codenames.phases import CodenamesPhase
from app.platform.exceptions import InvalidGameStateError, PermissionDeniedError

PLAYER_IDS = [f"p{i}" for i in range(4)]


@pytest.fixture
def started_engine():
    engine = CodenamesGameEngine("ROOM1")
    events = _run(engine.handle_command(StartGameCommand(player_id="p0", active_player_ids=PLAYER_IDS)))
    return engine, events


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def test_start_game_assigns_every_player_a_team_and_exactly_one_spymaster_per_team(started_engine):
    engine, events = started_engine

    assert all(isinstance(event, TeamAssignedEvent) for event in events)
    assert {event.player_id for event in events} == set(PLAYER_IDS)

    for team in (Team.RED, Team.BLUE):
        team_events = [e for e in events if e.team == team]
        assert len(team_events) == 2
        spymasters = [e for e in team_events if e.role == Role.SPYMASTER]
        assert len(spymasters) == 1


def test_start_game_deals_the_standard_9_8_7_1_distribution(started_engine):
    engine, _ = started_engine
    snapshot = engine.phase_snapshot()

    assert len(snapshot["board"]) == 25
    colors = [engine.get_spymaster_colors(pid) for pid in PLAYER_IDS]
    spymaster_colors = next(c for c in colors if c is not None)
    counts = {color: spymaster_colors.count(color) for color in {"red", "blue", "neutral", "assassin"}}
    assert counts["assassin"] == 1
    assert counts["neutral"] == 7
    assert sorted([counts["red"], counts["blue"]]) == [8, 9]


def test_phase_snapshot_hides_unrevealed_colors(started_engine):
    engine, _ = started_engine
    snapshot = engine.phase_snapshot()

    assert all(card["color"] is None for card in snapshot["board"])
    assert all(card["revealed"] is False for card in snapshot["board"])


def _team_and_role(events, player_id):
    event = next(e for e in events if e.player_id == player_id)
    return event.team, event.role


def _current_team(engine):
    phase = engine._state_machine.phase
    return Team.RED if phase == CodenamesPhase.RED_TURN else Team.BLUE


def _spymaster_and_guesser_for_current_team(engine, events):
    team = _current_team(engine)
    spymaster = next(e.player_id for e in events if e.team == team and e.role == Role.SPYMASTER)
    guesser = next(e.player_id for e in events if e.team == team and e.role == Role.GUESSER)
    return spymaster, guesser


def test_only_active_spymaster_can_give_a_clue(started_engine):
    engine, events = started_engine
    _, guesser = _spymaster_and_guesser_for_current_team(engine, events)

    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(GiveClueCommand(player_id=guesser, word="ANIMAL", number=2)))


def test_give_clue_produces_a_clue_given_event(started_engine):
    engine, events = started_engine
    spymaster, _ = _spymaster_and_guesser_for_current_team(engine, events)

    result = _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANIMAL", number=2)))

    assert len(result) == 1
    assert isinstance(result[0], ClueGivenEvent)
    assert result[0].word == "ANIMAL"
    assert result[0].number == 2


def test_cannot_give_a_second_clue_in_the_same_turn(started_engine):
    engine, events = started_engine
    spymaster, _ = _spymaster_and_guesser_for_current_team(engine, events)
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANIMAL", number=2)))

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="PLANT", number=1)))


def test_spymaster_cannot_guess(started_engine):
    engine, events = started_engine
    spymaster, _ = _spymaster_and_guesser_for_current_team(engine, events)
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANIMAL", number=2)))

    with pytest.raises(PermissionDeniedError):
        _run(engine.handle_command(MakeGuessCommand(player_id=spymaster, card_index=0)))


def test_guess_before_a_clue_is_rejected(started_engine):
    engine, events = started_engine
    _, guesser = _spymaster_and_guesser_for_current_team(engine, events)

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=0)))


def test_correct_guess_stays_on_the_same_team_until_max_guesses(started_engine):
    engine, events = started_engine
    team = _current_team(engine)
    spymaster, guesser = _spymaster_and_guesser_for_current_team(engine, events)
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANIMAL", number=1)))

    own_card_index = next(
        i for i, card in enumerate(engine._board) if card.color.value == team.value and not card.revealed
    )
    result = _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=own_card_index)))

    assert isinstance(result[0], CardRevealedEvent)
    assert engine.phase_snapshot()["current_team"] == team.value


def test_wrong_color_guess_switches_the_turn(started_engine):
    engine, events = started_engine
    team = _current_team(engine)
    other = Team.BLUE if team == Team.RED else Team.RED
    spymaster, guesser = _spymaster_and_guesser_for_current_team(engine, events)
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANIMAL", number=9)))

    wrong_card_index = next(
        i for i, card in enumerate(engine._board) if card.color.value == other.value and not card.revealed
    )
    _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=wrong_card_index)))

    assert engine.phase_snapshot()["current_team"] == other.value
    assert engine.phase_snapshot()["current_clue"] is None


def test_zero_clue_number_still_allows_exactly_one_bonus_guess(started_engine):
    engine, events = started_engine
    team = _current_team(engine)
    spymaster, guesser = _spymaster_and_guesser_for_current_team(engine, events)
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="MYSTERY", number=0)))

    own_card_index = next(
        i for i, card in enumerate(engine._board) if card.color.value == team.value and not card.revealed
    )
    _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=own_card_index)))

    assert engine.phase_snapshot()["current_team"] != team.value


def test_end_turn_switches_team_and_clears_the_clue(started_engine):
    engine, events = started_engine
    team = _current_team(engine)
    other = Team.BLUE if team == Team.RED else Team.RED
    spymaster, guesser = _spymaster_and_guesser_for_current_team(engine, events)
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANIMAL", number=3)))

    _run(engine.handle_command(EndTurnCommand(player_id=guesser)))

    assert engine.phase_snapshot()["current_team"] == other.value
    assert engine.phase_snapshot()["current_clue"] is None


def test_guessing_the_assassin_ends_the_game_for_the_other_team(started_engine):
    engine, events = started_engine
    team = _current_team(engine)
    other = Team.BLUE if team == Team.RED else Team.RED
    spymaster, guesser = _spymaster_and_guesser_for_current_team(engine, events)
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="DANGER", number=1)))

    assassin_index = next(i for i, card in enumerate(engine._board) if card.color == CardColor.ASSASSIN)
    result = _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=assassin_index)))

    game_over = next(e for e in result if isinstance(e, GameOverEvent))
    assert game_over.winning_side == other
    assert game_over.reason == "assassin"
    assert engine.phase_snapshot()["phase"] == "game_over"
    assert all(card["revealed"] for card in engine.phase_snapshot()["board"])


def test_revealing_a_teams_last_word_wins_even_when_guessed_by_the_opponent(started_engine):
    engine, events = started_engine
    team = _current_team(engine)
    other = Team.BLUE if team == Team.RED else Team.RED
    spymaster, guesser = _spymaster_and_guesser_for_current_team(engine, events)

    other_card_indices = [i for i, card in enumerate(engine._board) if card.color.value == other.value]
    for index in other_card_indices[:-1]:
        engine._board[index].revealed = True

    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANYTHING", number=9)))
    last_card_index = other_card_indices[-1]
    result = _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=last_card_index)))

    game_over = next(e for e in result if isinstance(e, GameOverEvent))
    assert game_over.winning_side == other
    assert game_over.reason == "all_words_found"


def test_cannot_reveal_an_already_revealed_card(started_engine):
    engine, events = started_engine
    team = _current_team(engine)
    spymaster, guesser = _spymaster_and_guesser_for_current_team(engine, events)
    own_card_index = next(
        i for i, card in enumerate(engine._board) if card.color.value == team.value and not card.revealed
    )
    _run(engine.handle_command(GiveClueCommand(player_id=spymaster, word="ANIMAL", number=1)))
    _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=own_card_index)))

    with pytest.raises(InvalidGameStateError):
        _run(engine.handle_command(MakeGuessCommand(player_id=guesser, card_index=own_card_index)))
