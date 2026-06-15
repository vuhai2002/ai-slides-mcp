"""Parse / format image-quota reset times.

Upstream's ``get_user_info`` returns ``reset_after`` as a RAW, unparsed value
whose exact shape is not guaranteed (ISO-8601 timestamp, epoch seconds, or a
relative duration). We normalize everything to an epoch float, and store/display
it as an ISO-8601 UTC string. Anything unparseable falls back to "now + 24h" so
a bad value can only DELAY a re-probe, never skip an account forever (the probe
remains the source of truth and overrides the hint).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# A value at/above this is read as an absolute epoch; below it, as a duration.
_PLAUSIBLE_EPOCH_FLOOR = 1_000_000_000  # ~2001-09-09


def _num_to_epoch(value: float, now: float) -> float:
    """Big number -> absolute epoch; small number -> duration-from-now."""
    if value >= _PLAUSIBLE_EPOCH_FLOOR:
        return value
    return now + max(0.0, value)


def to_epoch(raw: object, now: float) -> Optional[float]:
    """Best-effort parse of a reset value to epoch seconds.

    Returns None for empty / unparseable input (caller decides the fallback).
    """
    if raw is None:
        return None
    if isinstance(raw, bool):  # guard: bool is an int subclass
        return None
    if isinstance(raw, (int, float)):
        return _num_to_epoch(float(raw), now)
    s = str(raw).strip()
    if not s:
        return None
    try:  # numeric string -> epoch or duration
        return _num_to_epoch(float(s), now)
    except ValueError:
        pass
    try:  # ISO-8601 (tolerate a trailing Z)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def to_iso(epoch: float) -> str:
    """Epoch seconds -> ISO-8601 UTC string (storage + display form)."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def fallback(now: float, hours: float = 24.0) -> float:
    """Default reset epoch when upstream gave us nothing parseable."""
    return now + hours * 3600.0
