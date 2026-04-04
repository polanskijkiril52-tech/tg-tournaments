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
    display_name: str | None = None
    bio: str | None = None
    preferred_role: str | None = None
    steam_account_label: str | None = None
    steam_profile_url: str | None = None
    steam_id64: str | None = None
    steam_display_name: str | None = None
    steam_avatar_url: str | None = None
    dotabuff_url: str | None = None
    opendota_url: str | None = None

    class Config:
        from_attributes = True


class MeOut(UserOut):
    telegram_id: int | None = None
    first_name: str | None = None
    created_at: datetime | None = None


class ProfileUpdateIn(BaseModel):
    display_name: str | None = Field(default=None, max_length=64)
    bio: str | None = Field(default=None, max_length=500)
    preferred_role: str | None = Field(default=None, max_length=32)
    steam_account: str | None = Field(default=None, max_length=255)


class TournamentCreateIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    game: str = Field(default="Dota 2", max_length=50)
    format: str = Field(min_length=2, max_length=50)
    description: str | None = None
    max_teams: int | None = Field(default=None, ge=2, le=1024)
    start_at: datetime | None = None
    bracket_type: str = Field(default="single", pattern="^(single|double)$")
    rules_text: str | None = Field(default=None, max_length=4000)


class TournamentOut(BaseModel):
    id: int
    title: str
    game: str
    format: str
    description: str | None
    max_teams: int | None
    start_at: datetime | None
    status: str
    bracket_type: str = "single"
    rules_text: str | None = None
    created_at: datetime
    created_by_id: int

    class Config:
        from_attributes = True


class TeamCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class TeamJoinByCodeIn(BaseModel):
    invite_code: str = Field(min_length=1, max_length=64)


class TeamMemberRoleIn(BaseModel):
    role: str = Field(pattern="^(captain|player)$")


class TeamMemberOut(BaseModel):
    id: int
    user_id: int
    username: str | None = None
    display_name: str | None = None
    steam_account_label: str | None = None
    steam_profile_url: str | None = None
    steam_id64: str | None = None
    steam_display_name: str | None = None
    steam_avatar_url: str | None = None
    dotabuff_url: str | None = None
    opendota_url: str | None = None
    role: str
    joined_at: datetime | None = None

    class Config:
        from_attributes = True


class TeamOut(BaseModel):
    id: int
    name: str
    captain_user_id: int
    invite_code: str | None = None
    created_at: datetime
    members: list[TeamMemberOut] = []
    my_role: str | None = None

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
    bracket_group: str = "WB"
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


class MatchHistoryOut(BaseModel):
    id: int
    tournament_id: int
    tournament_title: str
    team1_name: str | None = None
    team2_name: str | None = None
    winner_name: str | None = None
    bracket_group: str = "WB"
    round: int
    position: int
    status: str
    created_at: datetime


class AdminResolveMatchIn(BaseModel):
    winner_team_id: int


class MatchActionOut(BaseModel):
    ok: bool
    message: str


class AdminOverviewOut(BaseModel):
    tournaments_count: int
    running_tournaments: int
    users_count: int
    teams_count: int
    matches_count: int
    recent_tournaments: list[TournamentOut]
