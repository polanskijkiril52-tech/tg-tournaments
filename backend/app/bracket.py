from __future__ import annotations

import math
from sqlalchemy.orm import Session

from .models import Match, Team, Tournament, TournamentTeam


def _next_power_of_two(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def generate_single_elimination(db: Session, tournament: Tournament) -> None:
    """Generate a single-elimination bracket for a tournament.

    Creates matches for all rounds, links them with next_match_id/next_slot,
    fills the first round with registered teams (by registration time), and
    auto-advances BYEs.
    """
    if tournament.status not in {"open", "registration", "draft"}:
        raise ValueError("Tournament cannot be started")

    # Safety: don't generate twice
    existing = (
        db.query(Match)
        .filter(Match.tournament_id == tournament.id)
        .first()
    )
    if existing:
        raise ValueError("Bracket already generated")

    participants = (
        db.query(TournamentTeam)
        .filter(TournamentTeam.tournament_id == tournament.id)
        .order_by(TournamentTeam.seed.is_(None), TournamentTeam.seed.asc(), TournamentTeam.created_at.asc())
        .all()
    )
    teams: list[Team] = [p.team for p in participants]
    if len(teams) < 2:
        raise ValueError("Need at least 2 teams")

    bracket_size = _next_power_of_two(len(teams))
    rounds_count = int(math.log2(bracket_size))

    rounds: dict[int, list[Match]] = {}

    # Create all matches (empty)
    for r in range(1, rounds_count + 1):
        matches_in_round = bracket_size // (2**r)
        rounds[r] = []
        for p in range(1, matches_in_round + 1):
            m = Match(
                tournament_id=tournament.id,
                round=r,
                position=p,
                status="pending",
            )
            db.add(m)
            rounds[r].append(m)

    db.flush()  # assign ids

    # Link matches to next round
    for r in range(1, rounds_count):
        for m in rounds[r]:
            next_pos = (m.position + 1) // 2
            next_slot = 1 if (m.position % 2 == 1) else 2
            nxt = rounds[r + 1][next_pos - 1]
            m.next_match_id = nxt.id
            m.next_slot = next_slot

    # Fill first round slots in order
    first = rounds[1]
    slots = bracket_size
    padded: list[Team | None] = teams + [None] * (slots - len(teams))
    for i, match in enumerate(first):
        t1 = padded[i * 2]
        t2 = padded[i * 2 + 1]
        match.team1_id = t1.id if t1 else None
        match.team2_id = t2.id if t2 else None
        if match.team1_id and match.team2_id:
            match.status = "ready"
        else:
            match.status = "pending"

    db.flush()

    # Auto-advance BYEs from round 1 and beyond
    for r in range(1, rounds_count + 1):
        for m in rounds[r]:
            _try_auto_bye(db, m)

    tournament.status = "running"


def _try_auto_bye(db: Session, match: Match) -> None:
    """If only one team is present, auto-finish the match and propagate."""
    if match.status == "finished":
        return

    t1 = match.team1_id
    t2 = match.team2_id
    if (t1 is None and t2 is None) or (t1 is not None and t2 is not None):
        # Not a bye
        if t1 is not None and t2 is not None and match.winner_id is None:
            match.status = "ready"
        return

    winner_id = t1 if t1 is not None else t2
    match.winner_id = winner_id
    match.status = "finished"
    propagate_winner(db, match)


def propagate_winner(db: Session, match: Match) -> None:
    """Put match.winner_id into the next match slot and auto-advance BYEs."""
    if not match.winner_id or not match.next_match_id or not match.next_slot:
        return
    nxt = db.query(Match).filter(Match.id == match.next_match_id).first()
    if not nxt:
        return

    if match.next_slot == 1:
        nxt.team1_id = match.winner_id
    else:
        nxt.team2_id = match.winner_id

    # Update status
    if nxt.team1_id and nxt.team2_id:
        nxt.status = "ready"
    else:
        nxt.status = "pending"

    db.flush()
    _try_auto_bye(db, nxt)
