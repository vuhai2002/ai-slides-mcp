import json

import pytest

from cgimg.auth import tokens


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tokens, "_auth_path", lambda: tmp_path / "auth.json")
    tokens.save({"access_token": "a", "refresh_token": "r", "id_token": "i"})
    loaded = tokens.load()
    assert loaded["access_token"] == "a"
    assert loaded["refresh_token"] == "r"


def test_load_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(tokens, "_auth_path", lambda: tmp_path / "nope.json")
    assert tokens.load() is None


def test_get_access_token_not_logged_in(tmp_path, monkeypatch):
    monkeypatch.setattr(tokens, "_auth_path", lambda: tmp_path / "none.json")
    with pytest.raises(RuntimeError, match="not logged in"):
        tokens.get_access_token()


def test_login_status_not_authed(tmp_path, monkeypatch):
    monkeypatch.setattr(tokens, "_auth_path", lambda: tmp_path / "none.json")
    assert tokens.login_status() == {"authed": False}


def test_refresh_for_force_bypasses_freshness(tmp_path, monkeypatch):
    import time

    monkeypatch.setattr(tokens, "_config_dir", lambda: tmp_path)  # store shares this dir
    calls = {"n": 0}

    def fake_req(rt):
        calls["n"] += 1
        return {"access_token": "fresh", "refresh_token": rt, "id_token": ""}

    monkeypatch.setattr(tokens, "_refresh_request", fake_req)
    acc = {"user_id": "uA", "access_token": "old", "refresh_token": "r",
           "saved_at": time.time()}  # fresh by saved_at

    assert tokens.refresh_for(dict(acc)) == "old"               # opaque token -> no refresh
    assert calls["n"] == 0
    assert tokens.refresh_for(dict(acc), force=True) == "fresh"  # forced -> refreshed
    assert calls["n"] == 1


def _jwt(exp: int) -> str:
    import base64
    import json
    p = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).rstrip(b"=").decode()
    return f"h.{p}.s"


def test_refresh_for_proactive_by_jwt_exp(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(tokens, "_config_dir", lambda: tmp_path)
    calls = {"n": 0}
    monkeypatch.setattr(tokens, "_refresh_request", lambda rt: calls.__setitem__(
        "n", calls["n"] + 1) or {"access_token": "fresh", "refresh_token": rt, "id_token": ""})
    now = int(time.time())
    far = {"user_id": "u", "access_token": _jwt(now + 10 * 86400), "refresh_token": "r"}
    near = {"user_id": "u2", "access_token": _jwt(now + 600), "refresh_token": "r"}

    assert tokens.refresh_for(dict(far)) == far["access_token"]  # far from expiry -> skip
    assert calls["n"] == 0
    assert tokens.refresh_for(dict(near)) == "fresh"             # within 24h skew -> refresh
    assert calls["n"] == 1


def test_refresh_for_stamps_error_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(tokens, "_config_dir", lambda: tmp_path)

    def boom(rt):
        raise RuntimeError("token refresh failed (HTTP 401)")

    monkeypatch.setattr(tokens, "_refresh_request", boom)
    acc = {"user_id": "u", "access_token": "old", "refresh_token": "r"}
    with pytest.raises(RuntimeError, match="refresh failed"):
        tokens.refresh_for(acc, force=True)
    assert acc.get("refresh_error_at")  # stamped so the pool backs it off
