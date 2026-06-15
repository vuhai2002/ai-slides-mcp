"""Tests for the v2 multi-account store + legacy migration (phase 01)."""
import json

import pytest

from cgimg.auth import store


@pytest.fixture
def auth_file(tmp_path, monkeypatch):
    p = tmp_path / "auth.json"
    monkeypatch.setattr(store, "_auth_path", lambda: p)
    return p


def test_missing_file_returns_empty(auth_file):
    assert store.load_accounts() == []


def test_corrupt_file_returns_empty(auth_file):
    auth_file.write_text("{not valid json", encoding="utf-8")
    assert store.load_accounts() == []


def test_legacy_migrates_and_rewrites(auth_file):
    auth_file.write_text(
        json.dumps({"access_token": "a", "refresh_token": "r",
                    "id_token": "i", "saved_at": 1}),
        encoding="utf-8",
    )
    accounts = store.load_accounts()
    assert len(accounts) == 1
    assert accounts[0]["access_token"] == "a"
    assert accounts[0]["user_id"] == ""  # legacy had no user_id
    # File is upgraded to v2 on disk.
    raw = json.loads(auth_file.read_text(encoding="utf-8"))
    assert raw["version"] == 2
    assert isinstance(raw["accounts"], list)


def test_v2_roundtrip(auth_file):
    store.save_accounts([{"user_id": "u1", "email": "a@x.com", "access_token": "t1"}])
    loaded = store.load_accounts()
    assert loaded[0]["user_id"] == "u1"
    assert loaded[0]["email"] == "a@x.com"


def test_upsert_replaces_by_user_id(auth_file):
    store.upsert_account({"user_id": "u1", "access_token": "old"})
    store.upsert_account({"user_id": "u1", "access_token": "new"})
    accounts = store.load_accounts()
    assert len(accounts) == 1
    assert accounts[0]["access_token"] == "new"


def test_upsert_appends_different_user_id(auth_file):
    store.upsert_account({"user_id": "u1", "access_token": "t1"})
    store.upsert_account({"user_id": "u2", "access_token": "t2"})
    assert len(store.load_accounts()) == 2


def test_upsert_empty_user_id_dedups_by_token(auth_file):
    store.upsert_account({"user_id": "", "access_token": "t1"})
    store.upsert_account({"user_id": "", "access_token": "t1"})
    assert len(store.load_accounts()) == 1


def test_upsert_merges_and_preserves_hints(auth_file):
    store.upsert_account({"user_id": "u1", "access_token": "t1", "last_quota": 5})
    store.upsert_account({"user_id": "u1", "access_token": "t2"})  # re-login, no hint
    acc = store.load_accounts()[0]
    assert acc["access_token"] == "t2"
    assert acc["last_quota"] == 5  # preserved across re-login


def test_remove_by_user_id(auth_file):
    store.upsert_account({"user_id": "u1", "access_token": "t1"})
    store.upsert_account({"user_id": "u2", "access_token": "t2"})
    assert store.remove_account("u1") == 1
    accounts = store.load_accounts()
    assert len(accounts) == 1
    assert accounts[0]["user_id"] == "u2"


def test_remove_by_email(auth_file):
    store.upsert_account({"user_id": "u1", "email": "a@x.com", "access_token": "t1"})
    assert store.remove_account("a@x.com") == 1
    assert store.load_accounts() == []


def test_remove_unknown_selector_is_noop(auth_file):
    store.upsert_account({"user_id": "u1", "access_token": "t1"})
    assert store.remove_account("nope") == 0
    assert len(store.load_accounts()) == 1


def test_remove_all(auth_file):
    store.upsert_account({"user_id": "u1", "access_token": "t1"})
    store.remove_all()
    assert store.load_accounts() == []


def test_upsert_stamps_saved_at(auth_file):
    store.upsert_account({"user_id": "u1", "access_token": "t1"})
    assert store.load_accounts()[0]["saved_at"] > 0
