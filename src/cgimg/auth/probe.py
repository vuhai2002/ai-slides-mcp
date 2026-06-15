"""Account probe helpers - the only place the pool reaches the network.

Kept separate from pool.py so the pool's selection logic stays pure and
unit-testable (tests inject a stub probe_fn). Token values are never logged.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

ProbeFn = Callable[[dict[str, Any]], dict[str, Any]]
RefreshFn = Callable[..., str]


def default_probe(account: dict[str, Any]) -> dict[str, Any]:
    """Call get_user_info with the account's access_token (lazy vendor import)."""
    import cgimg._vendor_path  # noqa: F401  (side effect: _vendor on sys.path)
    from services.openai_backend_api import OpenAIBackendAPI

    return OpenAIBackendAPI(access_token=account["access_token"]).get_user_info()


def probe_account(account: dict[str, Any], probe_fn: ProbeFn,
                  refresh_fn: Optional[RefreshFn] = None) -> dict[str, Any]:
    """Refresh-if-stale, call probe_fn, and force-refresh + retry ONCE if the
    backend rejects the token as invalid. Returns the raw info dict; re-raises if
    it still fails (the pool's select() then skips that account)."""
    if refresh_fn:
        try:
            account["access_token"] = refresh_fn(account) or account["access_token"]
        except Exception:
            pass
    try:
        return probe_fn(account)
    except Exception as exc:
        # Token expired / rejected: force a refresh (bypass freshness gate), retry once.
        if type(exc).__name__ != "InvalidAccessTokenError" or not refresh_fn:
            raise
        account["access_token"] = refresh_fn(account, force=True) or account["access_token"]
        return probe_fn(account)
