"""Real account probe - calls ChatGPT's get_user_info for one account.

Kept separate from pool.py so the pool's selection logic stays pure and
unit-testable (tests inject a stub). This is the ONLY place the pool reaches the
network. Token values are never logged.
"""
from __future__ import annotations

from typing import Any


def default_probe(account: dict[str, Any]) -> dict[str, Any]:
    """Call get_user_info with the account's access_token (lazy vendor import)."""
    import cgimg._vendor_path  # noqa: F401  (side effect: _vendor on sys.path)
    from services.openai_backend_api import OpenAIBackendAPI

    return OpenAIBackendAPI(access_token=account["access_token"]).get_user_info()
