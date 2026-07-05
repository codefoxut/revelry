from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    Achievement,
    Match,
    MatchParticipant,
    PlayerProfile,
    PlayerStatistics,
    SavedGameConfig,
    User,
    UserAchievement,
    UserSettings,
)


async def test_user_profile_relationship(session):
    user = User(username="alice")
    user.profile = PlayerProfile(display_name="Alice", avatar="fox")
    session.add(user)
    await session.commit()

    assert user.id is not None
    assert user.profile.user_id == user.id


async def test_username_must_be_unique(session):
    session.add(User(username="bob"))
    await session.commit()

    session.add(User(username="bob"))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_match_with_participants(session):
    user = User(username="carol")
    session.add(user)
    await session.flush()

    match = Match(
        game_type="mafia",
        room_code="ABCD",
        config_snapshot={"roles": ["mafia", "doctor", "detective", "villager"]},
        winning_faction="town",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    match.participants.append(
        MatchParticipant(
            user_id=user.id,
            display_name_snapshot="Carol",
            role="detective",
            is_winner=True,
            survived=True,
        )
    )
    session.add(match)
    await session.commit()

    assert len(match.participants) == 1
    assert match.participants[0].match_id == match.id


async def test_user_achievement_unique_constraint(session):
    user = User(username="dave")
    achievement = Achievement(key="first_win", name="First Win", description="Win your first match")
    session.add_all([user, achievement])
    await session.flush()

    session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
    await session.commit()

    session.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
    with pytest.raises(IntegrityError):
        await session.commit()


async def test_statistics_settings_and_saved_config(session):
    user = User(username="erin")
    session.add(user)
    await session.flush()

    session.add(PlayerStatistics(user_id=user.id, game_type="mafia", games_played=1, games_won=1))
    session.add(UserSettings(user_id=user.id, preferences={"sound": True}))
    session.add(
        SavedGameConfig(
            user_id=user.id,
            game_type="mafia",
            name="Classic 8-player",
            config={"roles": {"mafia": 2, "doctor": 1, "detective": 1}},
        )
    )
    await session.commit()
