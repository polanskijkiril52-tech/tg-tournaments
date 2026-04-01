from __future__ import annotations

import hmac
import hashlib
from urllib.parse import parse_qsl, unquote_plus


class TelegramInitDataError(Exception):
    pass


def verify_and_parse_init_data(init_data: str, bot_token: str) -> dict:
    """Verify Telegram Mini App initData and return parsed dict.

    Algorithm per Telegram docs:
    - initData is a query string with fields including `hash`
    - secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token)
    - data_check_string = '\n'.join(sorted(['key=value', ...] excluding hash))
    - expected_hash = HMAC_SHA256(key=secret_key, msg=data_check_string).hexdigest()
    - compare with received hash (hex)
    """
    if not init_data:
        raise TelegramInitDataError("Missing initData")

    # Telegram may URL-encode the whole initData string
    decoded = unquote_plus(init_data)

    pairs = list(parse_qsl(decoded, keep_blank_values=True))
    data = {k: v for k, v in pairs}

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise TelegramInitDataError("Missing hash in initData")

    # Build data-check-string
    items = [f"{k}={v}" for k, v in sorted(data.items(), key=lambda kv: kv[0])]
    data_check_string = "\n".join(items)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramInitDataError("Invalid initData hash")

    return data
