"""Tests for AccountPool selection / probe / decrement (phase 02)."""
import pytest

from cgimg.auth import pool as pool_mod
from cgimg.auth import reset_at, store

NOW = 1000.0


def _info(quota=None, unknown=False, user_id="", email="", type="free", restore_at=None):
    """Build a get_user_info-shaped dict."""
    return {"quota": quota, "image_quota_unknown": unknown, "user_id": user_id,
            "email": email, "type": type, "restore_at": restore_at}


class StubProbe:
    """Programmable probe: per-token queue of get_user_info results (last sticky)."""

    def __init__(self, scripts):
        self.scripts = {k: list(v) for k, v in scripts.items()}
        self.calls: dict[str, int] = {}

    def __call__(self, account):
        tok = account["access_token"]
        self.calls[tok] = self.calls.get(tok, 0) + 1
        q = self.scripts.get(tok) or [{}]
        return q.pop(0) if len(q) > 1 else q[0]


@pytest.fixture
def seeded(tmp_path, monkeypatch):
    """Point the store at a temp file and return a seeding helper."""
    monkeypatch.setattr(store, "_auth_path", lambda: tmp_path / "auth.json")

    def seed(accounts):
        store.save_accounts(accounts)
    return seed


def _pool(stub):
    return pool_mod.AccountPool(probe_fn=stub, now_fn=lambda: NOW)


def test_sticks_then_advances_then_raises(seeded):
    seeded([
        {"user_id": "uA", "access_token": "tokA"},
        {"user_id": "uB", "access_token": "tokB"},
    ])
    stub = StubProbe({
        "tokA": [_info(quota=2), _info(quota=0, restore_at=2000)],
        "tokB": [_info(quota=2), _info(quota=0, restore_at=2000)],
    })
    p = _pool(stub)

    assert p.select() == "tokA"          # probe A (quota 2)
    p.on_result("tokA", True)            # -> 1
    assert p.select() == "tokA"          # stick, no probe
    p.on_result("tokA", True)            # -> 0, A marked dead
    assert stub.calls["tokA"] == 1       # stuck, only probed once so far

    assert p.select() == "tokB"          # A dead -> probe B (quota 2)
    p.on_result("tokB", True)
    p.on_result("tokB", True)            # B -> 0, dead

    with pytest.raises(pool_mod.NoQuotaError) as exc:
        p.select()                       # all dead -> probe both, none usable
    assert "out of image quota" in str(exc.value)
    assert exc.value.restore_at_epoch is not None


def test_failure_does_not_decrement(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA"}])
    stub = StubProbe({"tokA": [_info(quota=2)]})
    p = _pool(stub)
    assert p.select() == "tokA"
    p.on_result("tokA", False)           # failure -> no decrement
    assert store.load_accounts()[0]["last_quota"] == 2


def test_hint_dead_account_skipped_without_probe(seeded):
    seeded([
        {"user_id": "uA", "access_token": "tokA",
         "restore_at": reset_at.to_iso(NOW + 10_000)},   # future -> dead
        {"user_id": "uB", "access_token": "tokB"},
    ])
    stub = StubProbe({"tokA": [_info(quota=5)], "tokB": [_info(quota=5)]})
    p = _pool(stub)
    assert p.select() == "tokB"
    assert stub.calls.get("tokA", 0) == 0    # never probed the dead one
    assert stub.calls["tokB"] == 1


def test_unknown_quota_is_tried_and_reprobed(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA"}])
    stub = StubProbe({"tokA": [_info(unknown=True, quota=0)]})
    p = _pool(stub)
    assert p.select() == "tokA"          # unknown -> usable
    assert p.select() == "tokA"          # not stickable -> re-probed
    assert stub.calls["tokA"] == 2


def test_probe_backfills_user_id_and_email(seeded):
    seeded([{"user_id": "", "access_token": "tokA"}])   # legacy migrated
    stub = StubProbe({"tokA": [_info(quota=3, user_id="u-new", email="a@x.com")]})
    p = _pool(stub)
    p.select()
    acc = store.load_accounts()[0]
    assert acc["user_id"] == "u-new"
    assert acc["email"] == "a@x.com"


def test_no_accounts_raises(seeded):
    seeded([])
    p = _pool(StubProbe({}))
    with pytest.raises(pool_mod.NoQuotaError, match="No accounts logged in"):
        p.select()


def test_is_exhausted(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA",
             "restore_at": reset_at.to_iso(NOW + 10_000)}])
    assert _pool(StubProbe({})).is_exhausted() is True
    seeded([{"user_id": "uB", "access_token": "tokB"}])
    assert _pool(StubProbe({})).is_exhausted() is False


def test_status_shape(seeded):
    seeded([{"user_id": "uA", "email": "a@x.com", "type": "free",
             "access_token": "tokA", "last_quota": 4}])
    rows = _pool(StubProbe({})).status()
    assert rows[0]["email"] == "a@x.com"
    assert rows[0]["remaining"] == 4
    assert rows[0]["alive"] is True


def test_current_token_selects_when_idle(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA"}])
    stub = StubProbe({"tokA": [_info(quota=2)]})
    p = _pool(stub)
    assert p.current_token() == "tokA"   # triggers select
    assert p.current_token() == "tokA"   # cached active, no extra probe
    assert stub.calls["tokA"] == 1


# ---- engine-adapter methods (phase 03) ----

def test_account_for_returns_email(seeded):
    seeded([{"user_id": "uA", "email": "a@x.com", "access_token": "tokA"}])
    p = _pool(StubProbe({}))
    assert p.account_for("tokA") == {"email": "a@x.com", "access_token": "tokA"}
    assert p.account_for("ghost") == {"email": "", "access_token": "ghost"}


def test_refresh_token_uses_refresh_fn(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA"}])
    p = pool_mod.AccountPool(probe_fn=StubProbe({}),
                             refresh_fn=lambda acc: "tokA-new", now_fn=lambda: NOW)
    assert p.refresh_token("tokA") == "tokA-new"


def test_refresh_token_unknown_or_no_fn_returns_same(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA"}])
    assert _pool(StubProbe({})).refresh_token("tokA") == "tokA"   # no refresh_fn
    assert _pool(StubProbe({})).refresh_token("ghost") == "ghost"  # unknown token


def test_probe_records_quota_reset_for_alive_account(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA"}])
    future = reset_at.to_iso(NOW + 3600)  # refills in 1h
    p = _pool(StubProbe({"tokA": [_info(quota=5, restore_at=future)]}))
    p.select()
    acc = store.load_accounts()[0]
    assert acc["last_quota"] == 5
    assert acc["quota_reset_at"] == future   # refill time captured (display)
    assert not acc.get("restore_at")         # but NOT benched - still alive
    rows = p.status()
    assert rows[0]["quota_reset_at"] == future
    assert rows[0]["alive"] is True


def test_disable_token_benches_account(seeded):
    seeded([{"user_id": "uA", "access_token": "tokA"}])
    p = _pool(StubProbe({}))
    p.disable_token("tokA")
    acc = store.load_accounts()[0]
    assert acc["restore_at"]
    assert p._hint_alive(acc) is False
