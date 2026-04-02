from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Team, TeamMember, User


def get_user_team_membership(db: Session, user: User) -> TeamMember | None:
    return db.query(TeamMember).filter(TeamMember.user_id == user.id).first()


def get_user_team(db: Session, user: User) -> Team | None:
    membership = get_user_team_membership(db, user)
    if not membership:
        return None
    return db.query(Team).filter(Team.id == membership.team_id).first()


def get_user_team_and_role(db: Session, user: User) -> tuple[Team | None, str | None]:
    membership = get_user_team_membership(db, user)
    if not membership:
        return None, None
    team = db.query(Team).filter(Team.id == membership.team_id).first()
    if not team:
        return None, None
    return team, membership.role


def is_team_captain(db: Session, team_id: int, user_id: int) -> bool:
    membership = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id, TeamMember.role == "captain")
        .first()
    )
    return membership is not None


def add_user_to_team(db: Session, *, team_id: int, user_id: int, role: str = "player") -> TeamMember:
    membership = TeamMember(team_id=team_id, user_id=user_id, role=role)
    db.add(membership)
    db.flush()
    db.refresh(membership)
    return membership


def remove_user_from_team(db: Session, *, team_id: int, user_id: int) -> bool:
    membership = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == team_id, TeamMember.user_id == user_id)
        .first()
    )
    if not membership:
        return False
    db.delete(membership)
    db.flush()
    return True


def list_team_members(db: Session, team_id: int) -> list[TeamMember]:
    return db.query(TeamMember).filter(TeamMember.team_id == team_id).order_by(TeamMember.id.asc()).all()
