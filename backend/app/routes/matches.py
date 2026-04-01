from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..bracket import propagate_winner
from ..deps import get_current_user, get_db
from ..models import Match, MatchReport, Team, Tournament, User
from ..schemas import MatchOut, MatchReportIn, MatchReportOut, MatchWithReportsOut


router = APIRouter(prefix="/matches", tags=["matches"])


def _get_user_team(db: Session, user: User) -> Team | None:
    return db.query(Team).filter(Team.captain_user_id == user.id).first()


@router.get("/next", response_model=MatchOut)
def next_match(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return the next match for the current user's team (captain).

    Priority: ready matches first, then pending.
    """
    team = _get_user_team(db, user)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Only running tournaments
    matches = (
        db.query(Match)
        .join(Tournament, Tournament.id == Match.tournament_id)
        .filter(
            Tournament.status == "running",
            Match.winner_id.is_(None),
            (Match.team1_id == team.id) | (Match.team2_id == team.id),
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


@router.get("/{match_id}", response_model=MatchWithReportsOut)
def get_match(match_id: int, db: Session = Depends(get_db)):
    m = db.query(Match).filter(Match.id == match_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Match not found")
    return m


@router.post("/{match_id}/report", response_model=MatchReportOut)
def report_match(
    match_id: int,
    data: MatchReportIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    tournament = db.query(Tournament).filter(Tournament.id == match.tournament_id).first()
    if not tournament or tournament.status != "running":
        raise HTTPException(status_code=400, detail="Tournament is not running")

    if match.status not in {"ready", "pending"} or match.winner_id is not None:
        raise HTTPException(status_code=400, detail="Match already finished")

    team = _get_user_team(db, user)
    if not team:
        raise HTTPException(status_code=400, detail="Create a team first")

    if team.id not in {match.team1_id, match.team2_id}:
        raise HTTPException(status_code=403, detail="You are not a participant of this match")

    # Simple sanity: avoid ties for now
    if data.score_team1 == data.score_team2:
        raise HTTPException(status_code=400, detail="Draw is not allowed")

    existing = (
        db.query(MatchReport)
        .filter(MatchReport.match_id == match.id, MatchReport.reporter_team_id == team.id)
        .first()
    )
    if existing:
        # Allow overwrite (MVP convenience)
        existing.score_team1 = data.score_team1
        existing.score_team2 = data.score_team2
        existing.proof_url = data.proof_url
        report = existing
    else:
        report = MatchReport(
            match_id=match.id,
            reporter_team_id=team.id,
            score_team1=data.score_team1,
            score_team2=data.score_team2,
            proof_url=data.proof_url,
        )
        db.add(report)

    db.flush()

    # If both teams reported same result -> finish
    reports = db.query(MatchReport).filter(MatchReport.match_id == match.id).all()
    if match.team1_id and match.team2_id and len(reports) >= 2:
        # Find latest report per team
        per_team: dict[int, MatchReport] = {}
        for r in sorted(reports, key=lambda x: x.created_at):
            per_team[r.reporter_team_id] = r

        if match.team1_id in per_team and match.team2_id in per_team:
            r1 = per_team[match.team1_id]
            r2 = per_team[match.team2_id]
            if (r1.score_team1, r1.score_team2) == (r2.score_team1, r2.score_team2):
                # Determine winner using score relative to team1/team2 slots
                if r1.score_team1 > r1.score_team2:
                    match.winner_id = match.team1_id
                else:
                    match.winner_id = match.team2_id
                match.status = "finished"
                propagate_winner(db, match)

    db.commit()
    db.refresh(report)
    return report
