"""Phase 04: login upsert, `cgimg accounts`, `cgimg logout`, MCP login_status."""
import json

import pytest

from cgimg import cli
from cgimg.auth import oauth_login, store, tokens


@pytest.fixture
def store_at(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_auth_path", lambda: tmp_path / "auth.json")
    return tmp_path


def test_login_complete_upserts_by_user_id(tmp_path, monkeypatch):
    monkeypatch.setattr(tokens, "_config_dir", lambda: tmp_path)  # pending + store dir
    monkeypatch.setattr(oauth_login, "exchange_code",
                        lambda code, verifier: {"access_token": "AT",
                                                "refresh_token": "RT", "id_token": "IT"})
    monkeypatch.setattr(oauth_login, "_account_from_tokens",
                        lambda toks: {"user_id": "uA", "email": "a@x.com",
                                      "type": "free", **toks})

    def _login(code):
        (tmp_path / "login_pending.json").write_text(
            json.dumps({"code_verifier": "v"}), encoding="utf-8")
        return oauth_login.complete(f"https://x/cb?code={code}")

    acc = _login("abc")
    assert acc["email"] == "a@x.com"
    assert len(store.load_accounts()) == 1
    _login("def")  # same user_id -> upsert, not a duplicate
    assert len(store.load_accounts()) == 1


def test_accounts_zero_message(store_at, capsys):
    rc = cli.main(["accounts"])
    assert rc == 0
    assert "No accounts logged in" in capsys.readouterr().out


def test_accounts_lists_with_live_probe(store_at, monkeypatch, capsys):
    import cgimg.auth.pool as pool_mod
    store.save_accounts([{"user_id": "uA", "email": "a@x.com", "access_token": "tokA"}])
    monkeypatch.setattr(pool_mod, "default_probe", lambda acc: {
        "quota": 7, "image_quota_unknown": False,
        "user_id": "uA", "email": "a@x.com", "type": "free"})
    rc = cli.main(["accounts"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "a@x.com" in out and "7" in out


def test_logout_one_then_all(store_at, capsys):
    store.save_accounts([
        {"user_id": "uA", "email": "a@x.com", "access_token": "t1"},
        {"user_id": "uB", "email": "b@x.com", "access_token": "t2"},
    ])
    assert cli.main(["logout", "a@x.com"]) == 0
    assert len(store.load_accounts()) == 1
    assert cli.main(["logout", "--all"]) == 0
    assert store.load_accounts() == []


def test_logout_without_selector_errors(store_at, capsys):
    store.save_accounts([{"user_id": "uA", "access_token": "t1"}])
    assert cli.main(["logout"]) == 2  # neither selector nor --all
    assert len(store.load_accounts()) == 1


def test_login_status_pool_shape(store_at, monkeypatch):
    from cgimg import server
    assert server.login_status() == {"authed": False, "accounts": [], "ready_count": 0}
    store.save_accounts([{"user_id": "uA", "email": "a@x.com", "type": "free",
                          "access_token": "t1", "last_quota": 3}])
    st = server.login_status()
    assert st["authed"] is True
    assert st["ready_count"] == 1
    assert st["accounts"][0]["email"] == "a@x.com"
