"""Multi-account image-quota pool: select / probe / decrement / persist.

Proactively probes ``get_user_info`` for remaining quota (the engine has no
rotate-on-quota path, so it must only receive a live account), sticks to one
account until it hits 0, then advances; persisted hints skip known-dead accounts
without a probe (the probe stays source of truth). Sequential; tokens never logged.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

from cgimg.auth import reset_at, store
from cgimg.auth.probe import default_probe

ProbeFn = Callable[[dict[str, Any]], dict[str, Any]]
RefreshFn = Callable[[dict[str, Any]], str]


class NoQuotaError(RuntimeError):
    """Every account is out of image quota. Carries the soonest reset epoch."""

    def __init__(self, message: str, restore_at_epoch: Optional[float] = None):
        super().__init__(message)
        self.restore_at_epoch = restore_at_epoch


class AccountPool:
    """Holds the account list and picks a quota-bearing account per image."""

    def __init__(
        self,
        probe_fn: Optional[ProbeFn] = None,
        refresh_fn: Optional[RefreshFn] = None,
        now_fn: Callable[[], float] = time.time,
    ):
        self._probe_fn = probe_fn or default_probe
        self._refresh_fn = refresh_fn  # per-account token refresh (wired phase 03)
        self._now = now_fn
        self._accounts = store.load_accounts()
        self._active_token: Optional[str] = None

    def _find(self, token: str) -> Optional[dict[str, Any]]:
        for a in self._accounts:
            if str(a.get("access_token") or "") == token:
                return a
        return None

    def _remaining(self, acc: dict[str, Any]) -> Optional[int]:
        q = acc.get("last_quota")
        return int(q) if isinstance(q, (int, float)) and not isinstance(q, bool) else None

    def _hint_alive(self, acc: dict[str, Any]) -> bool:
        """Cheap liveness from the persisted hint (no network)."""
        ra = acc.get("restore_at")
        if not ra:
            return True
        epoch = reset_at.to_epoch(ra, self._now())
        return epoch is None or epoch <= self._now()

    def _stickable(self, acc: dict[str, Any]) -> bool:
        rem = self._remaining(acc)
        return isinstance(rem, int) and rem > 0 and self._hint_alive(acc)

    def select(self) -> str:
        """Return a token with image quota (stick-until-exhausted); raise NoQuotaError when dry."""
        if self._active_token:
            acc = self._find(self._active_token)
            if acc is not None and self._stickable(acc):
                return self._active_token
        if not self._accounts:
            raise NoQuotaError("No accounts logged in - run `cgimg login`.")
        # Prefer hint-alive accounts; if none, probe all (a stale hint may lie).
        alive = [a for a in self._accounts if self._hint_alive(a)]
        for acc in (alive or list(self._accounts)):
            res = self.probe(acc)
            if res["unknown"] or (res["remaining"] or 0) > 0:
                self._active_token = str(acc.get("access_token") or "")
                return self._active_token
        self._active_token = None
        soonest = self._soonest_restore()
        raise NoQuotaError(self._exhausted_message(soonest), soonest)

    def current_token(self) -> str:
        """Active token, selecting one if needed (enhance shares this account)."""
        return self._active_token or self.select()

    def on_result(self, token: str, ok: bool) -> None:
        """Decrement local quota on success only; no cooldown on failure (a bool
        can't tell quota-exhaustion from a content-policy refusal)."""
        acc = self._find(token)
        if acc is None or not ok:
            return
        rem = self._remaining(acc)
        if rem is None:
            return  # unknown quota: cannot decrement; re-probed each select
        acc["last_quota"] = max(0, rem - 1)
        if acc["last_quota"] == 0:
            acc["restore_at"] = reset_at.to_iso(reset_at.fallback(self._now()))
            if self._active_token == token:
                self._active_token = None
        store.save_accounts(self._accounts)

    # Engine adapter - bound into the vendored shim via set_pool_provider.
    def account_for(self, token: str) -> dict[str, Any]:
        """Token -> minimal account dict so the engine can log the email."""
        acc = self._find(token)
        return {"email": (acc or {}).get("email") or "", "access_token": token}

    def refresh_token(self, token: str) -> str:
        """Best-effort refresh of that account's token; return new or same."""
        acc = self._find(token)
        if acc is None or not self._refresh_fn:
            return token
        try:
            return self._refresh_fn(acc) or token
        except Exception:
            return token

    def disable_token(self, token: str) -> None:
        """Bench an account whose token went invalid so select() skips it."""
        acc = self._find(token)
        if acc is None:
            return
        acc["restore_at"] = reset_at.to_iso(reset_at.fallback(self._now()))
        if self._active_token == token:
            self._active_token = None
        store.save_accounts(self._accounts)

    def probe(self, acc: dict[str, Any]) -> dict[str, Any]:
        """Probe get_user_info; update + persist the account (backfilling identity);
        return ``{remaining, unknown, restore_at_epoch}``."""
        if self._refresh_fn:
            try:
                acc["access_token"] = self._refresh_fn(acc) or acc["access_token"]
            except Exception:
                pass
        info = self._probe_fn(acc)
        unknown = bool(info.get("image_quota_unknown"))
        q = info.get("quota")
        remaining = int(q) if isinstance(q, (int, float)) and not isinstance(q, bool) else None
        now = self._now()
        for k in ("email", "user_id", "type"):
            if info.get(k):
                acc[k] = info[k]
        acc["probed_at"] = now
        # Informational backend refill time (display only; separate from restore_at).
        be = reset_at.to_epoch(info.get("restore_at"), now)
        acc["quota_reset_at"] = reset_at.to_iso(be) if be else None
        if unknown:
            acc["last_quota"] = None        # unknown counter -> try optimistically
            acc.pop("restore_at", None)
        else:
            acc["last_quota"] = remaining or 0
            if (remaining or 0) <= 0:
                epoch = reset_at.to_epoch(info.get("restore_at"), now) or reset_at.fallback(now)
                acc["restore_at"] = reset_at.to_iso(epoch)
            else:
                acc.pop("restore_at", None)
        store.save_accounts(self._accounts)
        return {"remaining": remaining, "unknown": unknown,
                "restore_at_epoch": reset_at.to_epoch(acc.get("restore_at"), now)}

    def is_exhausted(self) -> bool:
        """True when no account is (hint-)available - used by the deck layer."""
        return not self._accounts or not any(self._hint_alive(a) for a in self._accounts)

    def status(self, probe: bool = False) -> list[dict[str, Any]]:
        """Per-account summary. probe=True live-probes each first (CLI `accounts`);
        probe=False uses hints only - cheap, no network (MCP login_status)."""
        if probe:
            for acc in list(self._accounts):
                try:
                    self.probe(acc)
                except Exception:
                    pass
        return [
            {
                "email": a.get("email") or "",
                "user_id": a.get("user_id") or "",
                "type": a.get("type") or "free",
                "remaining": self._remaining(a),
                "restore_at": a.get("restore_at"),
                "quota_reset_at": a.get("quota_reset_at"),
                "alive": self._hint_alive(a),
            }
            for a in self._accounts
        ]

    def _soonest_restore(self) -> Optional[float]:
        now = self._now()
        epochs = [
            e for a in self._accounts
            if (e := reset_at.to_epoch(a.get("restore_at"), now)) is not None
        ]
        return min(epochs) if epochs else None

    def _exhausted_message(self, soonest: Optional[float]) -> str:
        base = f"All {len(self._accounts)} account(s) are out of image quota."
        return f"{base} Soonest reset at {reset_at.to_iso(soonest)}." if soonest else base
