import os
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..bracket import generate_double_elimination_4, generate_single_elimination
from ..config import settings
from ..deps import get_current_user, get_db, require_admin_strict
from ..models import Match, Team, Tournament, TournamentTeam, User
from ..schemas import BracketOut, TournamentCreateIn, TournamentJoinIn, TournamentOut, TournamentParticipantOut

router = APIRouter(prefix="/tournaments", tags=["tournaments"])
MINI_APP_URL = os.getenv("MINI_APP_URL", "").strip()


def _send_telegram_message(chat_id: int | None, text: str) -> None:
    if not chat_id or not settings.TELEGRAM_BOT_TOKEN:
        return
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": str(chat_id), "text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except Exception:
        return


def _captain_chat_id(team: Team | None) -> int | None:
    if not team or not team.captain or not team.captain.telegram_id:
        return None
    return int(team.captain.telegram_id)


def _match_url(match_id: int) -> str:
    if not MINI_APP_URL:
        return ""
    joiner = "&" if "?" in MINI_APP_URL else "?"
    return f"{MINI_APP_URL}{joiner}match_id={match_id}"


def _notify_match_ready(match: Match) -> None:
    if match.status != "ready" or not match.team1 or not match.team2:
        return
    link = _match_url(match.id)
    suffix = f"\n\nОткрыть матч: {link}" if link else ""
    text = (
        f"Матч готов.\nТурнир: {match.tournament.title}\n"
        f"Сетка: {match.bracket_group}\nРаунд: {match.round}\n"
        f"Соперник: {match.team1.name} vs {match.team2.name}{suffix}"
    )
    _send_telegram_message(_captain_chat_id(match.team1), text)
    _send_telegram_message(_captain_chat_id(match.team2), text)


def _notify_tournament_started(db: Session, tournament: Tournament) -> None:
    participants = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == tournament.id).order_by(TournamentTeam.created_at.asc()).all()
    common_text = f"Турнир стартовал.\n{tournament.title}\nФормат сетки: {tournament.bracket_type}"
    for p in participants:
        _send_telegram_message(_captain_chat_id(p.team), common_text)
    ready_matches = db.query(Match).filter(Match.tournament_id == tournament.id, Match.status == "ready").all()
    for m in ready_matches:
        _notify_match_ready(m)


@router.get("", response_model=list[TournamentOut])
def list_tournaments(db: Session = Depends(get_db)):
    return db.query(Tournament).order_by(Tournament.created_at.desc()).all()


@router.get("/{tournament_id}/bracket", response_model=BracketOut)
def get_bracket(tournament_id: int, db: Session = Depends(get_db)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    participants = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id).order_by(TournamentTeam.created_at.asc()).all()
    matches = db.query(Match).filter(Match.tournament_id == t.id).order_by(Match.round.asc(), Match.position.asc()).all()
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
        bracket_type=data.bracket_type,
        rules_text=data.rules_text,
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


@router.post("/{tournament_id}/check-in", response_model=TournamentParticipantOut)
def toggle_check_in(tournament_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    if t.status not in {"open", "registration", "draft"}:
        raise HTTPException(status_code=400, detail="Check-in is closed")
    team = db.query(Team).filter(Team.captain_user_id == user.id).first()
    if not team:
        raise HTTPException(status_code=400, detail="Create a team first")
    tt = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id, TournamentTeam.team_id == team.id).first()
    if not tt:
        raise HTTPException(status_code=404, detail="Team is not registered in this tournament")
    tt.checked_in = not bool(tt.checked_in)
    db.commit()
    db.refresh(tt)
    return tt


@router.post("/{tournament_id}/start")
def start_tournament(tournament_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    participants = db.query(TournamentTeam).filter(TournamentTeam.tournament_id == t.id).order_by(TournamentTeam.created_at.asc()).all()
    checked_in = [p for p in participants if p.checked_in]
    if checked_in:
        for p in participants:
            if not p.checked_in:
                db.delete(p)
        db.flush()
    try:
        if t.bracket_type == "double":
            generate_double_elimination_4(db, t)
        else:
            generate_single_elimination(db, t)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    db.refresh(t)
    _notify_tournament_started(db, t)
    return {"ok": True}


@router.delete("/{tournament_id}")
def delete_tournament(tournament_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    t = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Tournament not found")
    db.delete(t)
    db.commit()
    return {"ok": True}
