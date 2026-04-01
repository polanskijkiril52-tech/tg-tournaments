from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_db
from ..models import Team, User
from ..schemas import TeamCreateIn, TeamOut


router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=TeamOut)
def create_team(
    data: TeamCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Team name required")

    existing = db.query(Team).filter(Team.name == name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Team name already exists")

    # Simple rule for MVP: one captain -> one team
    has_team = db.query(Team).filter(Team.captain_user_id == user.id).first()
    if has_team:
        raise HTTPException(status_code=400, detail="You already have a team")

    team = Team(name=name, captain_user_id=user.id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/me", response_model=TeamOut)
def my_team(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    team = db.query(Team).filter(Team.captain_user_id == user.id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team
