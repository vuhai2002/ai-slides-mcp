"""force_utf8 lets non-ASCII output survive a cp1252-backed stream (Windows)."""
import io
import sys

from cgimg.console import force_utf8


def test_force_utf8_allows_non_ascii_on_cp1252_stream(monkeypatch):
    raw = io.BytesIO()
    # A cp1252 text stream cannot encode 'Đ'/'café'; force_utf8 flips it to UTF-8.
    stream = io.TextIOWrapper(raw, encoding="cp1252", newline="")
    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "stderr", stream)

    force_utf8()
    print("Đề tài / café")  # would raise UnicodeEncodeError on cp1252
    sys.stdout.flush()

    assert "Đề tài / café".encode("utf-8") in raw.getvalue()


def test_force_utf8_is_safe_when_unsupported(monkeypatch):
    # A stream without reconfigure() must not raise.
    class Dummy:
        pass

    monkeypatch.setattr(sys, "stdout", Dummy())
    monkeypatch.setattr(sys, "stderr", Dummy())
    force_utf8()  # no exception
