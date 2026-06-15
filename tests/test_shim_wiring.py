"""Phase 03 wiring: the vendored shim delegates to the injected pool callables,
text + image share one account, and the shim never imports cgimg."""
import ast
import importlib
import os
from pathlib import Path

import pytest

os.environ.setdefault("CHATGPT2API_AUTH_KEY", "cgimg-test")
import cgimg  # noqa: E402
import cgimg._vendor_path  # noqa: E402,F401  (side effect: _vendor on sys.path)

shim = importlib.import_module("services.account_service")

_SLOTS = ["_select", "_on_result", "_account_lookup", "_text_token", "_refresh", "_remove"]


@pytest.fixture(autouse=True)
def restore_provider():
    """Snapshot/restore the shim's global provider slots so tests don't leak."""
    saved = {n: getattr(shim, n) for n in _SLOTS}
    yield
    for n, v in saved.items():
        setattr(shim, n, v)


def test_set_pool_provider_delegates_every_method():
    calls = []
    shim.set_pool_provider(
        select=lambda: "img-tok",
        on_result=lambda t, ok: calls.append((t, ok)),
        account_lookup=lambda t: {"email": "a@x.com", "access_token": t},
        text_token=lambda: "txt-tok",
        refresh=lambda t: t + "-r",
        remove=lambda t: calls.append(("remove", t)),
    )
    svc = shim.account_service
    assert svc.get_available_access_token() == "img-tok"
    assert svc.get_text_access_token() == "txt-tok"
    assert svc.get_account("x")["email"] == "a@x.com"
    assert svc.refresh_access_token("t") == "t-r"
    svc.mark_image_result("x", True)
    svc.remove_invalid_token("dead")
    assert ("x", True) in calls and ("remove", "dead") in calls


def test_not_logged_in_raises_clear_error():
    shim.set_pool_provider(select=None, on_result=None, account_lookup=None,
                           text_token=None, refresh=None, remove=None)
    with pytest.raises(RuntimeError, match="not logged in"):
        shim.account_service.get_available_access_token()


def test_text_and_image_share_active_account(tmp_path, monkeypatch):
    from cgimg.auth import pool as pool_mod
    from cgimg.auth import store
    monkeypatch.setattr(store, "_auth_path", lambda: tmp_path / "auth.json")
    store.save_accounts([{"user_id": "uA", "access_token": "tokA"}])
    p = pool_mod.AccountPool(
        probe_fn=lambda acc: {"quota": 5, "image_quota_unknown": False, "user_id": "uA"},
        now_fn=lambda: 1000.0,
    )
    shim.set_pool_provider(
        select=p.select, on_result=p.on_result, account_lookup=p.account_for,
        text_token=p.current_token, refresh=p.refresh_token, remove=p.disable_token,
    )
    svc = shim.account_service
    assert svc.get_text_access_token() == "tokA"        # enhance selects first
    assert svc.get_available_access_token() == "tokA"   # image sticks to same


def test_image_generation_forced_sequential():
    # H1 guard: importing the engine flips the vendored parallel flag off so the
    # unlocked AccountPool singleton is never driven by concurrent threads (n>1).
    import cgimg.engine.generate  # noqa: F401
    from services.config import config
    assert config.image_parallel_generation is False


def test_shim_does_not_import_cgimg():
    # AST so a docstring mentioning "from cgimg" does not count - only real imports.
    src = (Path(cgimg._vendor_path.__file__).resolve().parent
           / "_vendor" / "services" / "account_service.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            assert all(not n.name.startswith("cgimg") for n in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("cgimg")
