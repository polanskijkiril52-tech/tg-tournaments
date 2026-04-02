from __future__ import annotations

import math
from sqlalchemy.orm import Session

from .models import Match, Team, Tournament, TournamentTeam


DE_WB = "WB"
DE_LB = "LB"
DE_GF = "GF"


def _next_power_of_two(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def get_seeded_teams(db: Session, tournament: Tournament) -> list[Team]:
    participants = (
        db.query(TournamentTeam)
        .filter(TournamentTeam.tournament_id == tournament.id)
        .order_by(
            TournamentTeam.seed.is_(None),
            TournamentTeam.seed.asc(),
            TournamentTeam.created_at.asc(),
        )
        .all()
    )
    return [p.team for p in participants]


def generate_single_elimination(db: Session, tournament: Tournament) -> None:
    if tournament.status not in {"open", "registration", "draft"}:
        raise ValueError("Tournament cannot be started")
    if db.query(Match).filter(Match.tournament_id == tournament.id).first():
        raise ValueError("Bracket already generated")

    teams = get_seeded_teams(db, tournament)
    if len(teams) < 2:
        raise ValueError("Need at least 2 teams")

    bracket_size = _next_power_of_two(len(teams))
    rounds_count = int(math.log2(bracket_size))
    rounds: dict[int, list[Match]] = {}

    for r in range(1, rounds_count + 1):
        matches_in_round = bracket_size // (2**r)
        rounds[r] = []
        for p in range(1, matches_in_round + 1):
            m = Match(
                tournament_id=tournament.id,
                round=r,
                position=p,
                status="pending",
                bracket_group=DE_WB,
            )
            db.add(m)
            rounds[r].append(m)

    db.flush()

    for r in range(1, rounds_count):
        for m in rounds[r]:
            next_pos = (m.position + 1) // 2
            next_slot = 1 if (m.position % 2 == 1) else 2
            nxt = rounds[r + 1][next_pos - 1]
            m.next_match_id = nxt.id
            m.next_slot = next_slot

    first = rounds[1]
    padded: list[Team | None] = teams + [None] * (bracket_size - len(teams))
    for i, match in enumerate(first):
        t1 = padded[i * 2]
        t2 = padded[i * 2 + 1]
        match.team1_id = t1.id if t1 else None
        match.team2_id = t2.id if t2 else None
        match.winner_id = None
        match.status = "ready" if match.team1_id and match.team2_id else "pending"

    db.flush()
    for r in range(1, rounds_count + 1):
        for m in rounds[r]:
            _try_auto_bye(db, m)
    tournament.status = "running"



def generate_double_elimination_4(db: Session, tournament: Tournament) -> None:
    """MVP double elimination for exactly 4 teams, without grand-final reset."""
    if tournament.status not in {"open", "registration", "draft"}:
        raise ValueError("Tournament cannot be started")
    if db.query(Match).filter(Match.tournament_id == tournament.id).first():
        raise ValueError("Bracket already generated")

    teams = get_seeded_teams(db, tournament)
    if len(teams) != 4:
        raise ValueError("Double elimination MVP currently supports exactly 4 teams")

    wb1 = Match(tournament_id=tournament.id, round=1, position=1, status="ready", bracket_group=DE_WB)
    wb2 = Match(tournament_id=tournament.id, round=1, position=2, status="ready", bracket_group=DE_WB)
    wb_final = Match(tournament_id=tournament.id, round=2, position=1, status="pending", bracket_group=DE_WB)
    lb1 = Match(tournament_id=tournament.id, round=101, position=1, status="pending", bracket_group=DE_LB)
    lb_final = Match(tournament_id=tournament.id, round=102, position=1, status="pending", bracket_group=DE_LB)
    grand_final = Match(tournament_id=tournament.id, round=103, position=1, status="pending", bracket_group=DE_GF)
    db.add_all([wb1, wb2, wb_final, lb1, lb_final, grand_final])
    db.flush()

    wb1.team1_id = teams[0].id
    wb1.team2_id = teams[1].id
    wb2.team1_id = teams[2].id
    wb2.team2_id = teams[3].id

    # winners bracket links
    wb1.next_match_id = wb_final.id
    wb1.next_slot = 1
    wb2.next_match_id = wb_final.id
    wb2.next_slot = 2

    # losers drop to LB
    wb1.loser_next_match_id = lb1.id
    wb1.loser_next_slot = 1
    wb2.loser_next_match_id = lb1.id
    wb2.loser_next_slot = 2

    # lb1 winner faces loser of wb final
    lb1.next_match_id = lb_final.id
    lb1.next_slot = 1
    wb_final.loser_next_match_id = lb_final.id
    wb_final.loser_next_slot = 2

    # final progression
    wb_final.next_match_id = grand_final.id
    wb_final.next_slot = 1
    lb_final.next_match_id = grand_final.id
    lb_final.next_slot = 2

    db.flush()
    tournament.status = "running"



def _set_match_ready_state(match: Match) -> None:
    match.winner_id = None if match.status != "finished" else match.winner_id
    if match.team1_id and match.team2_id:
        if match.winner_id is None:
            match.status = "ready"
    else:
        if match.winner_id is None:
            match.status = "pending"



def _place_team_in_slot(match: Match, slot: int, team_id: int | None) -> None:
    if slot == 1:
        match.team1_id = team_id
    else:
        match.team2_id = team_id



def propagate_result(db: Session, match: Match) -> None:
    if not match.winner_id:
        return

    loser_id = None
    if match.team1_id and match.team2_id:
        loser_id = match.team2_id if match.winner_id == match.team1_id else match.team1_id

    if match.next_match_id and match.next_slot:
        nxt = db.query(Match).filter(Match.id == match.next_match_id).first()
        if nxt and nxt.status != "finished":
            _place_team_in_slot(nxt, match.next_slot, match.winner_id)
            _set_match_ready_state(nxt)
            db.flush()
            _try_auto_bye(db, nxt)

    if loser_id and match.loser_next_match_id and match.loser_next_slot:
        nxt = db.query(Match).filter(Match.id == match.loser_next_match_id).first()
        if nxt and nxt.status != "finished":
            _place_team_in_slot(nxt, match.loser_next_slot, loser_id)
            _set_match_ready_state(nxt)
            db.flush()
            _try_auto_bye(db, nxt)



def _try_auto_bye(db: Session, match: Match) -> None:
    if match.status == "finished":
        return

    t1 = match.team1_id
    t2 = match.team2_id

    if t1 is None and t2 is None:
        match.winner_id = None
        match.status = "pending"
        return

    if t1 is not None and t2 is not None:
        if match.winner_id is None:
            match.status = "ready"
        return

    # only auto-finish if no unresolved feeder can still populate the empty slot
    empty_slot = 1 if t1 is None else 2
    feeder = (
        db.query(Match)
        .filter(
            ((Match.next_match_id == match.id) & (Match.next_slot == empty_slot)) |
            ((Match.loser_next_match_id == match.id) & (Match.loser_next_slot == empty_slot))
        )
        .first()
    )
    if feeder is not None and feeder.winner_id is None:
        match.winner_id = None
        match.status = "pending"
        return

    winner_id = t1 if t1 is not None else t2
    match.winner_id = winner_id
    match.status = "finished"
    propagate_result(db, match)
