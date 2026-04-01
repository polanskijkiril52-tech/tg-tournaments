from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Login/password auth
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Roles
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Telegram (ВАЖНО: BigInteger, потому что telegram_id может быть > 2_147_483_647)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # Optional profile fields
    first_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    tournaments_created: Mapped[list["Tournament"]] = relationship(
        back_populates="created_by", cascade="all,delete-orphan"
    )
class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(200), index=True)
    game: Mapped[str] = mapped_column(String(50), default="Dota 2")
    format: Mapped[str] = mapped_column(String(50))  # "1v1", "5v5", etc.
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    max_teams: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")  # open/running/finished

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    created_by: Mapped["User"] = relationship(back_populates="tournaments_created")

    participants: Mapped[list["TournamentTeam"]] = relationship(
        back_populates="tournament", cascade="all,delete-orphan"
    )

    matches: Mapped[list["Match"]] = relationship(
        back_populates="tournament", cascade="all,delete-orphan"
    )


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    captain_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    captain: Mapped["User"] = relationship()
    tournaments: Mapped[list["TournamentTeam"]] = relationship(
        back_populates="team", cascade="all,delete-orphan"
    )


class TournamentTeam(Base):
    __tablename__ = "tournament_teams"
    __table_args__ = (UniqueConstraint("tournament_id", "team_id", name="uq_tournament_team"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)

    checked_in: Mapped[bool] = mapped_column(Boolean, default=False)
    seed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tournament: Mapped["Tournament"] = relationship(back_populates="participants")
    team: Mapped["Team"] = relationship(back_populates="tournaments")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(ForeignKey("tournaments.id"), index=True)

    round: Mapped[int] = mapped_column(Integer, index=True)  # 1..N
    position: Mapped[int] = mapped_column(Integer, index=True)  # 1..matches_in_round

    team1_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    team2_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/ready/finished

    next_match_id: Mapped[Optional[int]] = mapped_column(ForeignKey("matches.id"), nullable=True)
    next_slot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1 or 2

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tournament: Mapped["Tournament"] = relationship(back_populates="matches")

    team1: Mapped[Optional["Team"]] = relationship(foreign_keys=[team1_id])
    team2: Mapped[Optional["Team"]] = relationship(foreign_keys=[team2_id])
    winner: Mapped[Optional["Team"]] = relationship(foreign_keys=[winner_id])

    next_match: Mapped[Optional["Match"]] = relationship(
        remote_side=[id],
        foreign_keys=[next_match_id],
    )

    reports: Mapped[list["MatchReport"]] = relationship(
        back_populates="match",
        cascade="all,delete-orphan",
    )


class MatchReport(Base):
    __tablename__ = "match_reports"
    __table_args__ = (UniqueConstraint("match_id", "reporter_team_id", name="uq_match_reporter"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    reporter_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)

    score_team1: Mapped[int] = mapped_column(Integer)
    score_team2: Mapped[int] = mapped_column(Integer)
    proof_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    match: Mapped["Match"] = relationship(back_populates="reports")
    reporter_team: Mapped["Team"] = relationship()