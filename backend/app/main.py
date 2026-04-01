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


# 🔥 Авто-фикс типа telegram_id -> BIGINT
def fix_telegram_id_type():
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT")
            )
    except Exception:
        # если таблицы нет или уже bigint — просто пропускаем
        pass


@app.on_event("startup")
def startup():
    # сначала пробуем исправить тип
    fix_telegram_id_type()

    # потом создаём таблицы если их нет
    Base.metadata.create_all(bind=engine)


# ✅ CORS
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