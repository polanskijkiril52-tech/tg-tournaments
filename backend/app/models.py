from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferred_role: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tournaments_created: Mapped[list["Tournament"]] = relationship(
        back_populates="created_by", cascade="all,delete-orphan"
    )


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    game: Mapped[str] = mapped_column(String(50), default="Dota 2")
    format: Mapped[str] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_teams: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")
    bracket_type: Mapped[str] = mapped_column(String(20), default="single")
    rules_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    invite_code: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    captain: Mapped["User"] = relationship(foreign_keys=[captain_user_id])
    tournaments: Mapped[list["TournamentTeam"]] = relationship(
        back_populates="team", cascade="all,delete-orphan"
    )
    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team", cascade="all,delete-orphan"
    )


class TeamMember(Base):
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(20), default="player")
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped["Team"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship()


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
    round: Mapped[int] = mapped_column(Integer, index=True)
    position: Mapped[int] = mapped_column(Integer, index=True)
    team1_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    team2_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    next_match_id: Mapped[Optional[int]] = mapped_column(ForeignKey("matches.id"), nullable=True)
    next_slot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    loser_next_match_id: Mapped[Optional[int]] = mapped_column(ForeignKey("matches.id"), nullable=True)
    loser_next_slot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bracket_group: Mapped[str] = mapped_column(String(20), default="WB")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tournament: Mapped["Tournament"] = relationship(back_populates="matches")
    team1: Mapped[Optional["Team"]] = relationship(foreign_keys=[team1_id])
    team2: Mapped[Optional["Team"]] = relationship(foreign_keys=[team2_id])
    winner: Mapped[Optional["Team"]] = relationship(foreign_keys=[winner_id])
    next_match: Mapped[Optional["Match"]] = relationship(remote_side=[id], foreign_keys=[next_match_id], post_update=True)
    loser_next_match: Mapped[Optional["Match"]] = relationship(remote_side=[id], foreign_keys=[loser_next_match_id], post_update=True)
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
