"""Multi-account image-quota pool: select / probe / decrement / persist.

Decides which ChatGPT account the engine uses per image: proactively probe
``get_user_info`` for remaining quota (the engine has no rotate-on-quota path,
so it must only receive a live account), stick to one account until its quota
hits 0, then advance. Persisted hints skip known-dead accounts without a probe;
the probe is always the source of truth. Sequential only; tokens never logged.
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

    # ---- small queries ---------------------------------------------------
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
            return True  # never probed / no known exhaustion
        epoch = reset_at.to_epoch(ra, self._now())
        return epoch is None or epoch <= self._now()

    def _stickable(self, acc: dict[str, Any]) -> bool:
        """Reuse the active account only when its known quota is positive."""
        rem = self._remaining(acc)
        return isinstance(rem, int) and rem > 0 and self._hint_alive(acc)

    # ---- selection -------------------------------------------------------
    def select(self) -> str:
        """Return an access_token with image quota, probing to confirm.

        Sticks to the active account while it has known quota; otherwise probes
        the next candidate. Raises ``NoQuotaError`` when all are exhausted.
        """
        if self._active_token:
            acc = self._find(self._active_token)
            if acc is not None and self._stickable(acc):
                return self._active_token

        if not self._accounts:
            raise NoQuotaError("Chưa đăng nhập account nào - chạy `cgimg login`.")

        # Prefer accounts the hint says are alive; if none, probe all (hint may
        # be stale - e.g. a fallback restore_at that has not really elapsed).
        alive = [a for a in self._accounts if self._hint_alive(a)]
        candidates = alive if alive else list(self._accounts)
        for acc in candidates:
            res = self.probe(acc)
            if res["unknown"] or (res["remaining"] or 0) > 0:
                self._active_token = str(acc.get("access_token") or "")
                return self._active_token

        self._active_token = None
        soonest = self._soonest_restore()
        raise NoQuotaError(self._exhausted_message(soonest), soonest)

    def current_token(self) -> str:
        """Active account's token, selecting one if needed (used by enhance)."""
        return self._active_token or self.select()

    # ---- result feedback -------------------------------------------------
    def on_result(self, token: str, ok: bool) -> None:
        """Record a generation result. Decrement local quota only on success.

        A failure consumes no quota and triggers NO cooldown in v1: the engine
        only passes a bool, so we cannot tell a quota error from a content-policy
        refusal or a ban - benching a healthy account on a one-off reject would
        be wrong. Real exhaustion is found by the proactive probe in ``select``.
        """
        acc = self._find(token)
        if acc is None or not ok:
            return
        rem = self._remaining(acc)
        if rem is None:
            return  # unknown quota: cannot decrement; re-probed each select
        acc["last_quota"] = max(0, rem - 1)
        if acc["last_quota"] == 0:
            # Approximate reset now; select()'s probe captures the real value
            # when all accounts are dead and it must report the soonest reset.
            acc["restore_at"] = reset_at.to_iso(reset_at.fallback(self._now()))
            if self._active_token == token:
                self._active_token = None
        store.save_accounts(self._accounts)

    # ---- probe -----------------------------------------------------------
    def probe(self, acc: dict[str, Any]) -> dict[str, Any]:
        """Refresh-if-needed, call get_user_info, update + persist the account.

        Returns ``{remaining, unknown, restore_at_epoch}``. Backfills
        email/user_id/type (fixes legacy accounts migrated with empty user_id).
        """
        if self._refresh_fn:
            try:
                acc["access_token"] = self._refresh_fn(acc) or acc["access_token"]
            except Exception:
                pass  # stale token still lets get_user_info report 401 cleanly
        info = self._probe_fn(acc)
        unknown = bool(info.get("image_quota_unknown"))
        q = info.get("quota")
        remaining = int(q) if isinstance(q, (int, float)) and not isinstance(q, bool) else None
        now = self._now()
        for k in ("email", "user_id", "type"):
            if info.get(k):
                acc[k] = info[k]
        acc["probed_at"] = now
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
        return {
            "remaining": remaining,
            "unknown": unknown,
            "restore_at_epoch": reset_at.to_epoch(acc.get("restore_at"), now),
        }

    # ---- reporting -------------------------------------------------------
    def is_exhausted(self) -> bool:
        """True when no account is (hint-)available - used by the deck layer."""
        return not self._accounts or not any(self._hint_alive(a) for a in self._accounts)

    def status(self) -> list[dict[str, Any]]:
        """Per-account summary (hint-based, no probe) for CLI / MCP."""
        return [
            {
                "email": a.get("email") or "",
                "user_id": a.get("user_id") or "",
                "type": a.get("type") or "free",
                "remaining": self._remaining(a),  # None = unknown
                "restore_at": a.get("restore_at"),
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
        n = len(self._accounts)
        if soonest:
            return (f"Tất cả {n} account đã hết quota ảnh. "
                    f"Account hồi phục sớm nhất lúc {reset_at.to_iso(soonest)}.")
        return f"Tất cả {n} account đã hết quota ảnh."
