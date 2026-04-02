from __future__ import annotations

import json
import time
from fastapi import Depends, HTTPException, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import SessionLocal
from .config import settings
from .auth.jwt import decode
from .models import User
from .telegram_init import verify_and_parse_init_data, TelegramInitDataError

bearer = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = creds.credentials
    try:
        payload = decode(token, settings.JWT_SECRET)
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _parse_telegram_user_id(x_init_data: str) -> int:
    """Parse Telegram user id from initData (expects non-empty initData string)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Server misconfigured: TELEGRAM_BOT_TOKEN not set")

    try:
        data = verify_and_parse_init_data(x_init_data, settings.TELEGRAM_BOT_TOKEN)
    except TelegramInitDataError as e:
        raise HTTPException(status_code=401, detail=str(e))

    # Optional: reject too old auth_date (24h)
    auth_date = data.get("auth_date")
    if auth_date:
        try:
            auth_date = int(auth_date)
            if int(time.time()) - auth_date > 60 * 60 * 24:
                raise HTTPException(status_code=401, detail="initData is too old")
        except ValueError:
            pass

    user_json = data.get("user")
    if not user_json:
        raise HTTPException(status_code=401, detail="initData missing user")

    try:
        user_obj = json.loads(user_json)
        tg_id = int(user_obj["id"])
        return tg_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid user in initData")


def get_telegram_user_id(x_init_data: str | None = Header(default=None, alias="X-Init-Data")) -> int:
    """Return Telegram user id after verifying initData signature (required)."""
    if not x_init_data:
        raise HTTPException(status_code=401, detail="Missing X-Init-Data header")
    return _parse_telegram_user_id(x_init_data)


def get_telegram_user_id_optional(
    x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
) -> int | None:
    """Return Telegram user id if initData is provided; otherwise None."""
    if not x_init_data:
        return None
    return _parse_telegram_user_id(x_init_data)


def require_admin_strict(
    user: User = Depends(get_current_user),
    tg_id: int | None = Depends(get_telegram_user_id_optional),
) -> User:
    """Strict admin in Telegram, with optional local dev fallback."""
    if settings.DEV_AUTH_ENABLED and tg_id is None and user.is_admin:
        return user

    if settings.ADMIN_TELEGRAM_ID is None:
        raise HTTPException(status_code=500, detail="Server misconfigured: ADMIN_TELEGRAM_ID not set")

    if tg_id is None:
        raise HTTPException(status_code=401, detail="Open the app from Telegram or use dev admin login")

    if tg_id != int(settings.ADMIN_TELEGRAM_ID):
        raise HTTPException(status_code=403, detail="Admin only")

    # Bind account to this Telegram id (anti-hijack)
    if user.telegram_id is None:
        user.telegram_id = tg_id
    elif user.telegram_id != tg_id:
        raise HTTPException(status_code=403, detail="This account is bound to another Telegram user")

    # keep flag for UI convenience
    user.is_admin = True
    return user
