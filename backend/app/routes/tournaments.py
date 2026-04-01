from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..bracket import generate_single_elimination
from ..deps import get_current_user, get_db, require_admin_strict
from ..models import Match, Team, Tournament, TournamentTeam, User
from ..schemas import BracketOut, CheckInOut, TournamentCreateIn, TournamentJoinIn, TournamentOut, TournamentParticipantOut

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.get("", response_model=list[TournamentOut])
def list_tournaments(db: Session = Depends(get_db)):
    return db.query(Tournament).order_by(Tournament.created_at.desc()).all()


@router.get("/{tournament_id}/bracket", response_model=BracketOut)
def get_bracket(tournament_id: int, db: Session = Depends(get_db)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    participants = (
        db.query(TournamentTeam)
        .filter(TournamentTeam.tournament_id == t.id)
        .order_by(TournamentTeam.created_at.asc())
        .all()
    )
    matches = (
        db.query(Match)
        .filter(Match.tournament_id == t.id)
        .order_by(Match.round.asc(), Match.position.asc())
        .all()
    )
    rounds: dict[int, list[Match]] = {}
    for m in matches:
        rounds.setdefault(m.round, []).append(m)

    return {"tournament": t, "participants": participants, "rounds": rounds}


@router.post("", response_model=TournamentOut)
def create_tournament(data: TournamentCreateIn, db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    t = Tournament(
        title=data.title.strip(),
        game=data.game.strip() if data.game else "Dota 2",
        format=data.format.strip(),
        description=data.description,
        max_teams=data.max_teams,
        start_at=data.start_at,
        created_by_id=admin.id,
        status="open",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.post("/{tournament_id}/join", response_model=TournamentParticipantOut)
def join_tournament(tournament_id: int, data: TournamentJoinIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if t.status not in {"open", "registration", "draft"}:
        raise HTTPException(status_code=400, detail="Tournament is not open for registration")

    team = db.query(Team).filter(Team.id == data.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    if team.captain_user_id != user.id:
        raise HTTPException(status_code=403, detail="Only captain can register the team")

    if t.max_teams is not None:
        cnt = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id).count()
        if cnt >= t.max_teams:
            raise HTTPException(status_code=400, detail="Tournament is full")

    existing = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id, TournamentTeam.team_id == team.id).first()
    if existing:
        return existing

    tt = TournamentTeam(tournament_id=t.id, team_id=team.id)
    db.add(tt)
    db.commit()
    db.refresh(tt)
    return tt


@router.post("/{tournament_id}/check-in", response_model=CheckInOut)
def toggle_check_in(tournament_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if t.status not in {"open", "registration", "draft"}:
        raise HTTPException(status_code=400, detail="Check-in is closed")

    team = db.query(Team).filter(Team.captain_user_id == user.id).first()
    if not team:
        raise HTTPException(status_code=400, detail="Create a team first")

    entry = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id, TournamentTeam.team_id == team.id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Team is not registered in this tournament")

    entry.checked_in = not bool(entry.checked_in)
    db.commit()
    return {"ok": True, "checked_in": entry.checked_in}


@router.post("/{tournament_id}/start")
def start_tournament(tournament_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")

    checked_in_count = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id, TournamentTeam.checked_in.is_(True)).count()
    if checked_in_count > 0:
        not_checked = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id, TournamentTeam.checked_in.is_(False)).all()
        for item in not_checked:
            db.delete(item)
        db.flush()

    try:
        generate_single_elimination(db, t)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    db.commit()
    return {"ok": True}


@router.delete("/{tournament_id}")
def delete_tournament(tournament_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    db.delete(t)
    db.commit()
    return {"ok": True}
