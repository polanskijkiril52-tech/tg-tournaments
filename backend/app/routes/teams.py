from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Team, TeamMember, User
from ..schemas import TeamCreateIn, TeamJoinByCodeIn, TeamMemberOut, TeamMemberRoleIn, TeamOut, MatchActionOut
from ..team_utils import add_user_to_team, get_user_team_membership, list_team_members, remove_user_from_team

router = APIRouter(prefix="/teams", tags=["teams"])


def _generate_invite_code() -> str:
    return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()


def _serialize_team(db: Session, team: Team, user: User | None = None) -> TeamOut:
    members_rows = list_team_members(db, team.id)
    members: list[TeamMemberOut] = []
    my_role = None
    for m in members_rows:
        if user and m.user_id == user.id:
            my_role = m.role
        members.append(
            TeamMemberOut(
                id=m.id,
                user_id=m.user_id,
                username=m.user.username if m.user else None,
                display_name=(m.user.display_name if m.user else None),
                role=m.role,
                joined_at=m.joined_at,
            )
        )
    return TeamOut(
        id=team.id,
        name=team.name,
        captain_user_id=team.captain_user_id,
        invite_code=team.invite_code,
        created_at=team.created_at,
        members=members,
        my_role=my_role,
    )


@router.post("", response_model=TeamOut)
def create_team(data: TeamCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Team name required")
    if db.query(Team).filter(Team.name == name).first():
        raise HTTPException(status_code=400, detail="Team name already exists")
    if get_user_team_membership(db, user):
        raise HTTPException(status_code=400, detail="You are already in a team")

    invite_code = _generate_invite_code()
    while db.query(Team).filter(Team.invite_code == invite_code).first():
        invite_code = _generate_invite_code()

    team = Team(name=name, captain_user_id=user.id, invite_code=invite_code)
    db.add(team)
    db.flush()
    add_user_to_team(db, team_id=team.id, user_id=user.id, role="captain")
    db.commit()
    db.refresh(team)
    return _serialize_team(db, team, user)


@router.get("/me", response_model=TeamOut)
def my_team(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = get_user_team_membership(db, user)
    if not membership:
        raise HTTPException(status_code=404, detail="Team not found")
    team = db.query(Team).filter(Team.id == membership.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return _serialize_team(db, team, user)


@router.post("/join-by-code", response_model=TeamOut)
def join_by_code(data: TeamJoinByCodeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if get_user_team_membership(db, user):
        raise HTTPException(status_code=400, detail="You are already in a team")
    code = data.invite_code.strip().upper()
    team = db.query(Team).filter(Team.invite_code == code).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    add_user_to_team(db, team_id=team.id, user_id=user.id, role="player")
    db.commit()
    db.refresh(team)
    return _serialize_team(db, team, user)


@router.post("/{team_id}/members/{member_user_id}/role", response_model=TeamOut)
def update_member_role(
    team_id: int,
    member_user_id: int,
    data: TeamMemberRoleIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.captain_user_id != user.id:
        raise HTTPException(status_code=403, detail="Captain only")

    member = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == member_user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    if data.role == "captain":
        old_captain = db.query(TeamMember).filter(TeamMember.team_id == team_id, TeamMember.user_id == team.captain_user_id).first()
        if old_captain:
            old_captain.role = "player"
        team.captain_user_id = member_user_id
    member.role = data.role

    db.add(team)
    db.add(member)
    db.commit()
    db.refresh(team)
    return _serialize_team(db, team, user)


@router.delete("/{team_id}/members/{member_user_id}", response_model=MatchActionOut)
def kick_member(
    team_id: int,
    member_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.captain_user_id != user.id:
        raise HTTPException(status_code=403, detail="Captain only")
    if member_user_id == user.id:
        raise HTTPException(status_code=400, detail="Use leave team or transfer captain first")

    removed = remove_user_from_team(db, team_id=team_id, user_id=member_user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    db.commit()
    return {"ok": True, "message": "Игрок удалён из состава"}


@router.post("/leave", response_model=MatchActionOut)
def leave_team(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    membership = get_user_team_membership(db, user)
    if not membership:
        raise HTTPException(status_code=404, detail="Team not found")
    team_id = membership.team_id

    if membership.role == "captain":
        total = db.query(TeamMember).filter(TeamMember.team_id == team_id).count()
        if total > 1:
            raise HTTPException(status_code=400, detail="Captain cannot leave until captain role transferred")
        team = db.query(Team).filter(Team.id == team_id).first()
        if team:
            db.delete(team)
            db.commit()
            return {"ok": True, "message": "Team deleted"}

    remove_user_from_team(db, team_id=team_id, user_id=user.id)
    db.commit()
    return {"ok": True, "message": "Left team"}
