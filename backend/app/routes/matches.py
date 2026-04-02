from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..bracket import propagate_result
from ..deps import get_current_user, get_db, require_admin_strict
from ..models import Match, MatchReport, Team, Tournament, User
from ..schemas import AdminResolveMatchIn, MatchActionOut, MatchHistoryOut, MatchOut, MatchReportOut, MatchReportIn, MatchWithReportsOut
from ..team_utils import get_user_team_and_role

router = APIRouter(prefix="/matches", tags=["matches"])


def _get_user_team(db: Session, user: User) -> Team | None:
    team, _role = get_user_team_and_role(db, user)
    return team


def _recompute_match_state(match: Match) -> None:
    match.winner_id = None
    match.status = "ready" if match.team1_id and match.team2_id else "pending"


@router.get("/next", response_model=MatchOut)
def next_match(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_user_team(db, user)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    matches = (
        db.query(Match)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .filter(
            Tournament.status == "running",
            Match.winner_id.is_(None),
            ((Match.team1_id == team.id) | (Match.team2_id == team.id)),
        )
        .order_by(Match.round.asc(), Match.position.asc(), Match.id.asc())
        .all()
    )
    if not matches:
        raise HTTPException(status_code=404, detail="No upcoming matches")
    for m in matches:
        if m.status == "ready":
            return m
    return matches[0]


@router.get("/history", response_model=list[MatchHistoryOut])
def history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    team = _get_user_team(db, user)
    if not team:
        return []
    matches = (
        db.query(Match)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .filter(Match.winner_id.is_not(None), ((Match.team1_id == team.id) | (Match.team2_id == team.id)))
        .order_by(Match.created_at.desc(), Match.id.desc())
        .all()
    )
    return [
        MatchHistoryOut(
            id=m.id,
            tournament_id=m.tournament_id,
            tournament_title=m.tournament.title if m.tournament else f"#{m.tournament_id}",
            team1_name=m.team1.name if m.team1 else None,
            team2_name=m.team2.name if m.team2 else None,
            winner_name=m.winner.name if m.winner else None,
            bracket_group=m.bracket_group,
            round=m.round,
            position=m.position,
            status=m.status,
            created_at=m.created_at,
        )
        for m in matches
    ]


@router.get("/{match_id}", response_model=MatchWithReportsOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    return m


@router.post("/{match_id}/report", response_model=MatchReportOut)
def report_match(match_id: int, data: MatchReportIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    tournament = db.query(Tournament).filter(Tournament.id == match.tournament_id).first()
    if not tournament or tournament.status != "running":
        raise HTTPException(status_code=400, detail="Tournament is not running")
    if match.status not in {"ready", "pending", "disputed"} or match.winner_id is not None:
        raise HTTPException(status_code=400, detail="Match already finished")
    team = _get_user_team(db, user)
    if not team:
        raise HTTPException(status_code=400, detail="Create or join a team first")
    if team.id not in {match.team1_id, match.team2_id}:
        raise HTTPException(status_code=403, detail="You are not a participant of this match")
    if data.score_team1 == data.score_team2:
        raise HTTPException(status_code=400, detail="Draw is not allowed")

    existing = db.query(MatchReport).filter(MatchReport.match_id == match.id, MatchReport.reporter_team_id == team.id).first()
    if existing:
        existing.score_team1 = data.score_team1
        existing.score_team2 = data.score_team2
        existing.proof_url = data.proof_url
        report = existing
    else:
        report = MatchReport(match_id=match.id, reporter_team_id=team.id, score_team1=data.score_team1, score_team2=data.score_team2, proof_url=data.proof_url)
        db.add(report)

    db.flush()
    reports = db.query(MatchReport).filter(MatchReport.match_id == match.id).all()
    if match.team1_id and match.team2_id and len(reports) >= 2:
        per_team: dict[int, MatchReport] = {r.reporter_team_id: r for r in sorted(reports, key=lambda x: x.created_at)}
        if match.team1_id in per_team and match.team2_id in per_team:
            r1 = per_team[match.team1_id]
            r2 = per_team[match.team2_id]
            if (r1.score_team1, r1.score_team2) == (r2.score_team1, r2.score_team2):
                match.winner_id = match.team1_id if r1.score_team1 > r1.score_team2 else match.team2_id
                match.status = "finished"
                propagate_result(db, match)
            else:
                match.status = "disputed"

    db.commit()
    db.refresh(report)
    return report


@router.post("/{match_id}/resolve", response_model=MatchWithReportsOut)
def resolve_match(match_id: int, data: AdminResolveMatchIn, db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    if data.winner_team_id not in {match.team1_id, match.team2_id}:
        raise HTTPException(status_code=400, detail="Winner must be one of the match teams")
    if match.winner_id is not None:
        raise HTTPException(status_code=400, detail="Match already finished")
    match.winner_id = data.winner_team_id
    match.status = "finished"
    propagate_result(db, match)
    db.commit()
    db.refresh(match)
    return match


@router.delete("/{match_id}", response_model=MatchActionOut)
def delete_match(match_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin_strict)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    if match.next_match_id and match.next_slot:
        nxt = db.query(Match).filter(Match.id == match.next_match_id).first()
        if nxt:
            if match.next_slot == 1:
                nxt.team1_id = None
            else:
                nxt.team2_id = None
            _recompute_match_state(nxt)

    if match.loser_next_match_id and match.loser_next_slot:
        nxt = db.query(Match).filter(Match.id == match.loser_next_match_id).first()
        if nxt:
            if match.loser_next_slot == 1:
                nxt.team1_id = None
            else:
                nxt.team2_id = None
            _recompute_match_state(nxt)

    feeders = db.query(Match).filter((Match.next_match_id == match.id) | (Match.loser_next_match_id == match.id)).all()
    for feeder in feeders:
        if feeder.next_match_id == match.id:
            feeder.next_match_id = None
            feeder.next_slot = None
        if feeder.loser_next_match_id == match.id:
            feeder.loser_next_match_id = None
            feeder.loser_next_slot = None

    db.delete(match)
    db.commit()
    return {"ok": True, "message": "Матч удалён"}
