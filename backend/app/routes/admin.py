from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import get_db, require_admin_strict
from ..models import Match, Team, Tournament, User
from ..schemas import AdminOverviewOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=AdminOverviewOut)
def overview(db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    recent = db.query(Tournament).order_by(Tournament.created_at.desc()).limit(6).all()
    return {
        "tournaments_count": db.query(Tournament).count(),
        "running_tournaments": db.query(Tournament).filter(Tournament.status == "running").count(),
        "users_count": db.query(User).count(),
        "teams_count": db.query(Team).count(),
        "matches_count": db.query(Match).count(),
        "recent_tournaments": recent,
    }
