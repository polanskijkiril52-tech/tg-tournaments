from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from ..schemas import AuthOut, RegisterIn, LoginIn, MeOut
from ..auth.jwt import create
from ..config import settings
from ..deps import get_db, get_current_user, get_telegram_user_id, get_telegram_user_id_optional
from ..models import User
from ..telegram_init import TelegramInitDataError, verify_and_parse_init_data

router = APIRouter()

# ✅ Без bcrypt (нет лимита 72 байта и меньше проблем на хостингах)
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


@router.get("/me", response_model=MeOut)
def me(
    user: User = Depends(get_current_user),
    tg_id: int | None = Depends(get_telegram_user_id_optional),
):
    # If initData is present, bind account to tg_id (one-time)
    if tg_id is not None:
        if user.telegram_id is None:
            user.telegram_id = tg_id
        elif user.telegram_id != tg_id:
            raise HTTPException(status_code=403, detail="This account is bound to another Telegram user")

    is_admin = (
        settings.ADMIN_TELEGRAM_ID is not None
        and (tg_id == int(settings.ADMIN_TELEGRAM_ID) if tg_id is not None else user.telegram_id == int(settings.ADMIN_TELEGRAM_ID))
    )

    return {"id": user.id, "username": user.username, "is_admin": bool(is_admin)}


@router.post("/auth/register", response_model=AuthOut)
def register(
    data: RegisterIn,
    db: Session = Depends(get_db),
    tg_id: int | None = Depends(get_telegram_user_id_optional),
):
    username = data.username.strip()

    if not username or not data.password:
        raise HTTPException(status_code=400, detail="Username and password required")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(
        username=username,
        password_hash=pwd.hash(data.password),
        telegram_id=tg_id,
        is_admin=False,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create(user.id, settings.JWT_SECRET, settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return {"access_token": token}


@router.post("/auth/login", response_model=AuthOut)
def login(
    data: LoginIn,
    db: Session = Depends(get_db),
    tg_id: int | None = Depends(get_telegram_user_id_optional),
):
    username = data.username.strip()

    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # If this account is already bound to a Telegram user, require initData.
    if user.telegram_id is not None and tg_id is None:
        raise HTTPException(status_code=401, detail="Open the app from Telegram to login")

    # Bind account to tg id if not set; otherwise protect against hijack
    if tg_id is not None:
        if user.telegram_id is None:
            user.telegram_id = tg_id
            db.commit()
        elif user.telegram_id != tg_id:
            raise HTTPException(status_code=403, detail="This account is bound to another Telegram user")

    token = create(user.id, settings.JWT_SECRET, settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return {"access_token": token}


@router.post("/auth/telegram", response_model=AuthOut)
def telegram_login(
    db: Session = Depends(get_db),
    x_init_data: str = Header(..., alias="X-Init-Data"),
):
    """Login/signup via Telegram Mini App initData.

    - validates signature
    - finds user by telegram_id or creates a new one
    - returns JWT access token
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Server misconfigured: TELEGRAM_BOT_TOKEN not set")

    try:
        parsed = verify_and_parse_init_data(x_init_data, settings.TELEGRAM_BOT_TOKEN)
    except TelegramInitDataError as e:
        raise HTTPException(status_code=401, detail=str(e))

    user_json = parsed.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="initData missing user")

    try:
        tg_user = json.loads(user_json)
        tg_id = int(tg_user["id"])
        tg_username = (tg_user.get("username") or "").strip()
        first_name = (tg_user.get("first_name") or "").strip() or None
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user in initData")

    user = db.query(User).filter(User.telegram_id == tg_id).first()
    if not user:
        # Prefer Telegram username if it's present (not guaranteed)
        base_username = tg_username if tg_username else f"tg_{tg_id}"
        base_username = base_username[:64]
        username = base_username
        i = 1
        while db.query(User).filter(User.username == username).first():
            i += 1
            suffix = f"_{i}"
            username = (base_username[: (64 - len(suffix))] + suffix)[:64]

        # We still need a password_hash for the existing username/password login
        random_pw = secrets.token_urlsafe(16)
        user = User(
            username=username,
            password_hash=pwd.hash(random_pw),
            telegram_id=tg_id,
            first_name=first_name,
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # keep some profile fields up to date
        changed = False
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            db.commit()

    token = create(user.id, settings.JWT_SECRET, settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return {"access_token": token}
