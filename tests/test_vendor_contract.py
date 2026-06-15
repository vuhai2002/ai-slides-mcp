"""Contract test guarding the single-account shim against upstream drift.

The vendored engine talks to `account_service` (our single-account shim in
src/cgimg/_vendor/services/account_service.py). The shim implements exactly the
methods the engine calls; anything else falls through to a no-op `__getattr__`.

That no-op is a trap: if a future upstream re-vendor starts calling a NEW
account_service method whose RETURN VALUE is consumed, the catch-all would
silently return None and break image generation in a hard-to-debug way.

This test fails loudly in that case - every `account_service.<method>(` call
found in the vendored code must be a method EXPLICITLY defined on the shim, not
merely absorbed by the catch-all. When it fails after an update, either add an
explicit handler to the shim or extend CATCHALL_OK below with a justification.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# config.py instantiates `config` at import time and needs an auth key present.
os.environ.setdefault("CHATGPT2API_AUTH_KEY", "cgimg-import-test")

import cgimg._vendor_path  # noqa: E402,F401  (side effect: puts _vendor on sys.path)

_VENDOR = Path(cgimg._vendor_path.__file__).resolve().parent / "_vendor"

# Methods that are intentionally allowed to hit the no-op __getattr__ catch-all
# because their return value is never consumed (pure side-effect calls). Keep
# empty unless a reviewed update proves a call is genuinely fire-and-forget.
CATCHALL_OK: set[str] = set()

_CALL_RE = re.compile(r"account_service\.([A-Za-z_][A-Za-z0-9_]*)\s*\(")


def _explicit_shim_methods() -> set[str]:
    import importlib

    mod = importlib.import_module("services.account_service")
    cls = type(mod.account_service)
    # Names defined directly on the shim class, excluding dunders (so the
    # __getattr__ catch-all itself is not counted as an explicit handler).
    return {
        name
        for name, value in vars(cls).items()
        if callable(value) and not name.startswith("__")
    }


def _called_methods() -> dict[str, set[str]]:
    """Map method name -> set of files that call account_service.<method>(."""
    calls: dict[str, set[str]] = {}
    for py in _VENDOR.rglob("*.py"):
        if py.name == "account_service.py":
            continue  # the shim itself, not a caller
        text = py.read_text(encoding="utf-8", errors="ignore")
        for method in _CALL_RE.findall(text):
            calls.setdefault(method, set()).add(py.name)
    return calls


def test_set_token_provider_exists():
    """generate.py wires the runtime token via this hook - it must exist."""
    import importlib

    mod = importlib.import_module("services.account_service")
    assert hasattr(mod, "set_token_provider"), (
        "account_service.set_token_provider missing - the engine cannot inject "
        "the logged-in token without it."
    )


def test_every_account_service_call_is_explicitly_handled():
    explicit = _explicit_shim_methods()
    called = _called_methods()

    unhandled = {
        method: files
        for method, files in called.items()
        if method not in explicit and method not in CATCHALL_OK
    }

    assert not unhandled, (
        "Vendored code calls account_service methods the single-account shim does "
        "NOT define explicitly (they would silently no-op via __getattr__):\n"
        + "\n".join(
            f"  - account_service.{m}()  called in: {', '.join(sorted(f))}"
            for m, f in sorted(unhandled.items())
        )
        + "\n\nFix: add an explicit handler in "
        "src/cgimg/_vendor/services/account_service.py, or add the method to "
        "CATCHALL_OK in this test if its return value is provably unused."
    )
