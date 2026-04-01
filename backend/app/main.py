from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .db import Base, engine
from .routes.auth import router as auth_router
from .routes.teams import router as teams_router
from .routes.matches import router as matches_router
from .routes.tournaments import router as tournaments_router

app = FastAPI(title="Tournament Mini App API")


def apply_safe_schema_fixes():
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT"))
    except Exception:
        pass
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE tournament_teams ADD COLUMN checked_in BOOLEAN DEFAULT FALSE"))
    except Exception:
        pass


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    apply_safe_schema_fixes()


origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
if not origins:
    origins = ["*"]

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


@app.get("/")
def root():
    return {"ok": True}


@app.get("/ping")
def ping():
    return {"status": "ok"}
