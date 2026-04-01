import time
import jwt
from jwt import PyJWTError


def create(user_id: int, secret: str, expires_in_seconds: int = 86400) -> str:
    return jwt.encode(
        {"sub": str(user_id), "exp": int(time.time()) + int(expires_in_seconds)},
        secret,
        algorithm="HS256",
    )


def decode(token: str, secret: str) -> dict:
    # Raises PyJWTError on invalid/expired token
    return jwt.decode(token, secret, algorithms=["HS256"])
