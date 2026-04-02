from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .db import Base, engine
from .routes.admin import router as admin_router
from .routes.auth import router as auth_router
from .routes.teams import router as teams_router
from .routes.matches import router as matches_router
from .routes.tournaments import router as tournaments_router

app = FastAPI(title="Tournament Mini App API")


def apply_safe_schema_fixes():
    stmts = [
        "ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT",
        "ALTER TABLE users ADD COLUMN display_name VARCHAR(64)",
        "ALTER TABLE users ADD COLUMN bio TEXT",
        "ALTER TABLE users ADD COLUMN preferred_role VARCHAR(32)",
        "ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT NOW()",
        "ALTER TABLE tournament_teams ADD COLUMN checked_in BOOLEAN DEFAULT FALSE",
        "ALTER TABLE teams ADD COLUMN invite_code VARCHAR(64)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_teams_invite_code ON teams (invite_code)",
        "ALTER TABLE tournaments ADD COLUMN bracket_type VARCHAR(20) DEFAULT 'single'",
        "ALTER TABLE tournaments ADD COLUMN rules_text TEXT",
        "ALTER TABLE matches ADD COLUMN loser_next_match_id INTEGER REFERENCES matches(id)",
        "ALTER TABLE matches ADD COLUMN loser_next_slot INTEGER",
        "ALTER TABLE matches ADD COLUMN bracket_group VARCHAR(20) DEFAULT 'WB'",
        "CREATE TABLE IF NOT EXISTS team_members (id SERIAL PRIMARY KEY, team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, role VARCHAR(20) NOT NULL DEFAULT 'player', joined_at TIMESTAMP DEFAULT NOW(), CONSTRAINT uq_team_member UNIQUE (team_id, user_id))",
    ]
    for stmt in stmts:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass

    try:
        with engine.begin() as conn:
            rows = conn.execute(text("SELECT id, captain_user_id FROM teams")).fetchall()
            for team_id, captain_user_id in rows:
                if captain_user_id is None:
                    continue
                conn.execute(
                    text("INSERT INTO team_members (team_id, user_id, role) VALUES (:team_id, :user_id, 'captain') ON CONFLICT (team_id, user_id) DO NOTHING"),
                    {"team_id": team_id, "user_id": captain_user_id},
                )
                code = conn.execute(text("SELECT invite_code FROM teams WHERE id = :team_id"), {"team_id": team_id}).scalar()
                if not code:
                    conn.execute(text("UPDATE teams SET invite_code = upper(substr(md5(random()::text), 1, 8)) WHERE id = :team_id"), {"team_id": team_id})
    except Exception:
        pass


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    apply_safe_schema_fixes()


origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(teams_router)
app.include_router(tournaments_router)
app.include_router(matches_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {"ok": True}


@app.get("/ping")
def ping():
    return {"status": "ok"}
