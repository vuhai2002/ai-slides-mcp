"""Tests for defensive reset-time parsing (phase 02)."""
from datetime import datetime, timezone

from cgimg.auth import reset_at

NOW = 1000.0


# These test the raw parser (_parse, no clamp) - to_epoch additionally clamps
# implausibly-far results (covered separately below).
def test_iso_timestamp():
    epoch = reset_at._parse("2030-01-01T00:00:00Z", NOW)
    assert epoch == datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp()


def test_iso_without_tz_assumed_utc():
    epoch = reset_at._parse("2030-01-01T00:00:00", NOW)
    assert epoch == datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp()


def test_absolute_epoch_number():
    assert reset_at._parse(2_000_000_000, NOW) == 2_000_000_000.0


def test_epoch_as_string():
    assert reset_at._parse("2000000000", NOW) == 2_000_000_000.0


def test_small_number_is_duration_from_now():
    assert reset_at.to_epoch(3600, NOW) == NOW + 3600
    assert reset_at.to_epoch("86400", NOW) == NOW + 86400


def test_junk_returns_none():
    assert reset_at.to_epoch("not-a-date", NOW) is None


def test_empty_and_none_return_none():
    assert reset_at.to_epoch("", NOW) is None
    assert reset_at.to_epoch(None, NOW) is None
    assert reset_at.to_epoch("   ", NOW) is None


def test_bool_is_not_treated_as_number():
    assert reset_at.to_epoch(True, NOW) is None


def test_fallback_is_24h():
    assert reset_at.fallback(NOW) == NOW + 24 * 3600


def test_iso_roundtrip():
    epoch = NOW + 5000
    assert reset_at.to_epoch(reset_at.to_iso(epoch), NOW) == epoch


def test_millisecond_value_clamped_to_24h():
    # 1 day in ms (86_400_000), misread as seconds, would be ~1000 days out ->
    # clamped to now+24h so a bad upstream format can't bench an account for years.
    assert reset_at.to_epoch(86_400_000, NOW) == NOW + 24 * 3600


def test_far_future_epoch_clamped_to_24h():
    assert reset_at.to_epoch(99_999_999_999, NOW) == NOW + 24 * 3600


def test_value_within_7_days_not_clamped():
    assert reset_at.to_epoch(3600, NOW) == NOW + 3600
