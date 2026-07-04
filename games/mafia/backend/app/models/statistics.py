from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class PlayerStatistics(Base):
    """Denormalized per-user, per-game aggregate stats, updated after each
    Match completes — avoids scanning match history for a profile page.
    """

    __tablename__ = "player_statistics"
    __table_args__ = (UniqueConstraint("user_id", "game_type", name="uq_user_game_stats"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    game_type: Mapped[str] = mapped_column(String(32))
    games_played: Mapped[int] = mapped_column(default=0)
    games_won: Mapped[int] = mapped_column(default=0)
    times_survived: Mapped[int] = mapped_column(default=0)
