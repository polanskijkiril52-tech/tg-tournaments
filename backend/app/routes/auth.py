from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Header
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth.jwt import create
from ..config import settings
from ..deps import get_current_user, get_db, get_telegram_user_id_optional
from ..models import User
from ..schemas import AuthOut, LoginIn, MeOut, ProfileUpdateIn, RegisterIn
from ..steam_utils import (
    SteamAccountError,
    build_dotabuff_url,
    build_opendota_url,
    fetch_steam_profile_summary,
    normalize_steam_account,
)
from ..telegram_init import TelegramInitDataError, verify_and_parse_init_data

router = APIRouter()
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


class DevLoginIn(BaseModel):
    username: str = Field(default="testuser", min_length=2, max_length=64)
    is_admin: bool = False


def serialize_me(user: User, tg_id: int | None = None) -> dict:
    tg_admin = False
    if settings.ADMIN_TELEGRAM_ID is not None:
        admin_tg_id = int(settings.ADMIN_TELEGRAM_ID)
        tg_admin = (tg_id == admin_tg_id) if tg_id is not None else (user.telegram_id == admin_tg_id)

    return {
        "id": user.id,
        "username": user.username,
        "is_admin": bool(user.is_admin or tg_admin),
        "display_name": user.display_name,
        "bio": user.bio,
        "preferred_role": user.preferred_role,
        "steam_account_label": user.steam_account_label,
        "steam_profile_url": user.steam_profile_url,
        "steam_id64": user.steam_id64,
        "steam_display_name": user.steam_display_name,
        "steam_avatar_url": user.steam_avatar_url,
        "dotabuff_url": build_dotabuff_url(user.steam_id64),
        "opendota_url": build_opendota_url(user.steam_id64),
        "telegram_id": user.telegram_id,
        "first_name": user.first_name,
        "created_at": user.created_at,
    }


@router.get("/me", response_model=MeOut)
def me(
    user: User = Depends(get_current_user),
    tg_id: int | None = Depends(get_telegram_user_id_optional),
):
    if tg_id is not None:
        if user.telegram_id is None:
            user.telegram_id = tg_id
        elif user.telegram_id != tg_id:
            raise HTTPException(status_code=403, detail="This account is bound to another Telegram user")

    return serialize_me(user, tg_id=tg_id)


@router.put("/me/profile", response_model=MeOut)
def update_profile(
    data: ProfileUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    tg_id: int | None = Depends(get_telegram_user_id_optional),
):
    if tg_id is not None and user.telegram_id not in {None, tg_id}:
        raise HTTPException(status_code=403, detail="This account is bound to another Telegram user")

    user.display_name = (data.display_name or "").strip() or None
    user.bio = (data.bio or "").strip() or None
    user.preferred_role = (data.preferred_role or "").strip() or None

    steam_raw = (data.steam_account or "").strip()
    if steam_raw:
        try:
            steam_profile_url, steam_account_label = normalize_steam_account(steam_raw)
        except SteamAccountError as e:
            raise HTTPException(status_code=400, detail=str(e))

        summary = fetch_steam_profile_summary(steam_profile_url)
        user.steam_profile_url = steam_profile_url
        user.steam_account_label = steam_account_label
        user.steam_id64 = summary.get("steam_id64") or (steam_account_label if steam_account_label and steam_account_label.isdigit() else None)
        user.steam_display_name = summary.get("steam_display_name") or user.steam_display_name
        user.steam_avatar_url = summary.get("steam_avatar_url") or user.steam_avatar_url
    else:
        user.steam_profile_url = None
        user.steam_account_label = None
        user.steam_id64 = None
        user.steam_display_name = None
        user.steam_avatar_url = None

    db.add(user)
    db.commit()
    db.refresh(user)
    return serialize_me(user, tg_id=tg_id)


@router.post("/auth/register", response_model=AuthOut)
def register(data: RegisterIn, db: Session = Depends(get_db), tg_id: int | None = Depends(get_telegram_user_id_optional)):
    username = data.username.strip()
    if not username or not data.password:
        raise HTTPException(status_code=400, detail="Username and password required")
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    user = User(username=username, password_hash=pwd.hash(data.password), telegram_id=tg_id, is_admin=False)
    db.add(user)
    db.commit()
    db.refresh(user)
    token = create(user.id, settings.JWT_SECRET, settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return {"access_token": token}


@router.post("/auth/login", response_model=AuthOut)
def login(data: LoginIn, db: Session = Depends(get_db), tg_id: int | None = Depends(get_telegram_user_id_optional)):
    username = data.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not pwd.verify(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.telegram_id is not None and tg_id is None:
        raise HTTPException(status_code=401, detail="Open the app from Telegram to login")
    if tg_id is not None:
        if user.telegram_id is None:
            user.telegram_id = tg_id
            db.commit()
        elif user.telegram_id != tg_id:
            raise HTTPException(status_code=403, detail="This account is bound to another Telegram user")
    token = create(user.id, settings.JWT_SECRET, settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return {"access_token": token}


@router.post("/auth/dev-login", response_model=AuthOut)
def dev_login(data: DevLoginIn, db: Session = Depends(get_db)):
    if not settings.DEV_AUTH_ENABLED:
        raise HTTPException(status_code=403, detail="Dev auth is disabled")
    username = data.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user:
        random_pw = secrets.token_urlsafe(16)
        user = User(username=username, password_hash=pwd.hash(random_pw), telegram_id=None, is_admin=bool(data.is_admin))
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.is_admin = bool(data.is_admin)
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create(user.id, settings.JWT_SECRET, settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return {"access_token": token}


@router.post("/auth/telegram", response_model=AuthOut)
def telegram_login(db: Session = Depends(get_db), x_init_data: str = Header(..., alias="X-Init-Data")):
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
        base_username = tg_username if tg_username else f"tg_{tg_id}"
        base_username = base_username[:64]
        username = base_username
        i = 1
        while db.query(User).filter(User.username == username).first():
            i += 1
            suffix = f"_{i}"
            username = (base_username[: (64 - len(suffix))] + suffix)[:64]
        random_pw = secrets.token_urlsafe(16)
        user = User(
            username=username,
            password_hash=pwd.hash(random_pw),
            telegram_id=tg_id,
            first_name=first_name,
            display_name=first_name,
            is_admin=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        changed = False
        if first_name and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if first_name and not user.display_name:
            user.display_name = first_name
            changed = True
        if changed:
            db.commit()
    token = create(user.id, settings.JWT_SECRET, settings.ACCESS_TOKEN_EXPIRE_SECONDS)
    return {"access_token": token}
