from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _generate_uuid() -> str:
    return str(uuid.uuid4())


class Match(Base):
    """A completed game, persisted for history/stats after the in-memory
    game ends — active game state itself never touches this table.

    `game_type`/`winning_faction` are free strings rather than enums so any
    future Revelry game can be recorded here, not just Mafia.
    """

    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_generate_uuid)
    game_type: Mapped[str] = mapped_column(String(32), index=True)
    room_code: Mapped[str] = mapped_column(String(16))
    config_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    winning_faction: Mapped[str | None] = mapped_column(String(32))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    participants: Mapped[list["MatchParticipant"]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class MatchParticipant(Base):
    """One player's record within a Match — role/outcome, kept as a snapshot
    (display name, role string) so it stays accurate even if the profile or
    role catalog changes later.
    """

    __tablename__ = "match_participants"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    display_name_snapshot: Mapped[str] = mapped_column(String(32))
    role: Mapped[str | None] = mapped_column(String(32))
    is_winner: Mapped[bool] = mapped_column(default=False)
    survived: Mapped[bool] = mapped_column(default=False)

    match: Mapped["Match"] = relationship(back_populates="participants")
