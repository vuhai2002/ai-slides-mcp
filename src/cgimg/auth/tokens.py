"""Single-account token store + refresh against OpenAI's OAuth endpoint."""
from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from curl_cffi import requests

_CLIENT_ID = "app_2SKx67EdpoN0G6j64rFvigXD"
_TOKEN_URL = "https://auth.openai.com/oauth/token"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")
# Refresh if the stored access_token is older than this (seconds). 12h < 24h keepalive.
_REFRESH_AFTER = 12 * 3600


def _config_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~/.config")
    return Path(base) / "cgimg"


def _auth_path() -> Path:
    return _config_dir() / "auth.json"


def save(tok: dict[str, Any]) -> None:
    p = _auth_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tok = {**tok, "saved_at": time.time()}
    p.write_text(json.dumps(tok, indent=2), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def load() -> Optional[dict[str, Any]]:
    p = _auth_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _refresh_request(refresh_token: str) -> dict[str, str]:
    resp = requests.post(
        _TOKEN_URL,
        headers={"Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": _UA},
        data={"grant_type": "refresh_token",
              "refresh_token": refresh_token,
              "client_id": _CLIENT_ID},
        timeout=60,
    )
    data = resp.json() if resp.text else {}
    if resp.status_code != 200 or not data.get("access_token"):
        raise RuntimeError(f"token refresh failed (HTTP {resp.status_code})")
    return data


def get_access_token(force: bool = False) -> str:
    """Return a valid access_token, refreshing if stale or forced.
    Raises RuntimeError if not logged in."""
    tok = load()
    if tok is None:
        raise RuntimeError("not logged in — run `cgimg login`")
    stale = (time.time() - tok.get("saved_at", 0)) > _REFRESH_AFTER
    if force or stale:
        if not tok.get("refresh_token"):
            raise RuntimeError("no refresh_token stored — run `cgimg login` again")
        new = _refresh_request(tok["refresh_token"])
        tok = {**tok, **new}
        save(tok)
    return tok["access_token"]


def refresh_for(account: dict[str, Any], force: bool = False) -> str:
    """Refresh ONE pool account's access_token via its refresh_token.

    Used by the multi-account pool. Returns the current token unchanged when it is
    still fresh (and not forced) or there is no refresh_token; otherwise refreshes
    and persists the new tokens through the v2 store (deduped by user_id).
    force=True refreshes even when the token still looks fresh - used to recover a
    token the backend just rejected as invalid.
    """
    from cgimg.auth import store  # local import avoids a store<->tokens cycle

    tok = str(account.get("access_token") or "")
    fresh = (time.time() - (account.get("saved_at") or 0)) <= _REFRESH_AFTER
    if (fresh and not force) or not account.get("refresh_token"):
        return tok
    new = _refresh_request(account["refresh_token"])
    account["access_token"] = new.get("access_token") or tok
    if new.get("refresh_token"):
        account["refresh_token"] = new["refresh_token"]
    if new.get("id_token"):
        account["id_token"] = new["id_token"]
    account["saved_at"] = time.time()
    store.upsert_account(account)
    return account["access_token"]


def login_status() -> dict[str, Any]:
    tok = load()
    if tok is None:
        return {"authed": False}
    return {"authed": True,
            "has_refresh": bool(tok.get("refresh_token")),
            "saved_at": tok.get("saved_at")}
