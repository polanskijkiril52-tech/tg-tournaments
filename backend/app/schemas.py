from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AuthOut(BaseModel):
    access_token: str


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=4, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool

    class Config:
        from_attributes = True


class MeOut(UserOut):
    pass


class TournamentCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    game: str = Field(default="Dota 2", max_length=50)
    format: str = Field(min_length=2, max_length=50)
    description: str | None = None
    max_teams: int | None = Field(default=None, ge=2, le=1024)
    start_at: datetime | None = None


class TournamentOut(BaseModel):
    id: int
    title: str
    game: str
    format: str
    description: str | None
    max_teams: int | None
    start_at: datetime | None
    status: str
    created_at: datetime
    created_by_id: int

    class Config:
        from_attributes = True


class TeamCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class TeamOut(BaseModel):
    id: int
    name: str
    captain_user_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TournamentJoinIn(BaseModel):
    team_id: int


class TournamentParticipantOut(BaseModel):
    id: int
    tournament_id: int
    team: TeamOut
    checked_in: bool
    seed: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class MatchOut(BaseModel):
    id: int
    tournament_id: int
    round: int
    position: int
    team1: TeamOut | None
    team2: TeamOut | None
    winner: TeamOut | None
    status: str
    next_match_id: int | None
    next_slot: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class BracketOut(BaseModel):
    tournament: TournamentOut
    participants: list[TournamentParticipantOut]
    rounds: dict[int, list[MatchOut]]


class MatchReportIn(BaseModel):
    score_team1: int = Field(ge=0, le=100)
    score_team2: int = Field(ge=0, le=100)
    proof_url: str | None = Field(default=None, max_length=500)


class MatchReportOut(BaseModel):
    id: int
    match_id: int
    reporter_team_id: int
    score_team1: int
    score_team2: int
    proof_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class MatchWithReportsOut(MatchOut):
    reports: list[MatchReportOut] = []


class AdminResolveMatchIn(BaseModel):
    winner_team_id: int


class CheckInOut(BaseModel):
    ok: bool
    checked_in: bool
