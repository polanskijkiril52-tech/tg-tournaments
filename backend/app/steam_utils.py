from __future__ import annotations

import re
import urllib.request
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import urlparse


_STEAM_ID64_RE = re.compile(r"^7656119\d{10}$")
_STEAM_VANITY_RE = re.compile(r"^[A-Za-z0-9_-]{2,64}$")
_STEAM64_BASE = 76561197960265728


class SteamAccountError(ValueError):
    pass


def normalize_steam_account(value: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    raw = (value or "").strip()
    if not raw:
        return None, None

    if raw.isdigit():
        if not _STEAM_ID64_RE.fullmatch(raw):
            raise SteamAccountError("Steam ID должен быть в формате 17 цифр")
        return f"https://steamcommunity.com/profiles/{raw}", raw

    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        host = (parsed.netloc or "").lower()
        if host not in {"steamcommunity.com", "www.steamcommunity.com"}:
            raise SteamAccountError("Укажите ссылку на steamcommunity.com")
        parts = [p for p in (parsed.path or "").split("/") if p]
        if len(parts) < 2 or parts[0] not in {"id", "profiles"}:
            raise SteamAccountError("Поддерживаются ссылки вида /id/<name> или /profiles/<steamid64>")
        account_type, account_value = parts[0], parts[1]
        if account_type == "profiles":
            if not _STEAM_ID64_RE.fullmatch(account_value):
                raise SteamAccountError("Steam profile URL должен содержать 17-значный Steam ID")
        else:
            if not _STEAM_VANITY_RE.fullmatch(account_value):
                raise SteamAccountError("Steam vanity должен содержать только буквы, цифры, _ или -")
        return f"https://steamcommunity.com/{account_type}/{account_value}", account_value

    if _STEAM_VANITY_RE.fullmatch(raw):
        return f"https://steamcommunity.com/id/{raw}", raw

    raise SteamAccountError("Укажите Steam vanity, Steam ID64 или ссылку на профиль Steam")


def steam_account_id_from_id64(steam_id64: Optional[str]) -> Optional[int]:
    if not steam_id64 or not _STEAM_ID64_RE.fullmatch(steam_id64):
        return None
    return int(steam_id64) - _STEAM64_BASE


def build_dotabuff_url(steam_id64: Optional[str]) -> Optional[str]:
    account_id = steam_account_id_from_id64(steam_id64)
    if account_id is None:
        return None
    return f"https://www.dotabuff.com/players/{account_id}"


def build_opendota_url(steam_id64: Optional[str]) -> Optional[str]:
    account_id = steam_account_id_from_id64(steam_id64)
    if account_id is None:
        return None
    return f"https://www.opendota.com/players/{account_id}"


def fetch_steam_profile_summary(profile_url: Optional[str]) -> dict[str, Optional[str]]:
    if not profile_url:
        return {
            "steam_id64": None,
            "steam_display_name": None,
            "steam_avatar_url": None,
        }

    xml_url = profile_url.rstrip("/") + "/?xml=1"
    req = urllib.request.Request(
        xml_url,
        headers={
            "User-Agent": "Mozilla/5.0 TournamentMiniApp/1.0",
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
    except Exception:
        return {
            "steam_id64": None,
            "steam_display_name": None,
            "steam_avatar_url": None,
        }

    steam_id64 = (root.findtext("steamID64") or "").strip() or None
    display_name = (root.findtext("steamID") or "").strip() or None
    avatar_url = (root.findtext("avatarFull") or root.findtext("avatarMedium") or root.findtext("avatarIcon") or "").strip() or None
    return {
        "steam_id64": steam_id64,
        "steam_display_name": display_name,
        "steam_avatar_url": avatar_url,
    }
