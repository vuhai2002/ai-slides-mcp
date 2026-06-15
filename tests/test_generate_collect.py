"""Unit tests for generate._collect_saved (the n-cap save loop, issue #5)."""
import base64

from cgimg.engine import generate


class _Out:
    """Minimal stand-in for the vendored ImageOutput (.kind/.data/.text)."""

    def __init__(self, kind, data=None, text=None):
        self.kind = kind
        self.data = data or []
        self.text = text


def _b64() -> str:
    return base64.b64encode(b"\x89PNG\r\n\x1a\nfake-bytes").decode()


def test_collect_saved_caps_at_n(tmp_path):
    # Backend returns 2 variants but n=1 -> only 1 file saved (the #5 bug).
    out = _Out("result", data=[{"b64_json": _b64()}, {"b64_json": _b64()}])
    saved, _ = generate._collect_saved([out], n=1, out_dir=str(tmp_path))
    assert len(saved) == 1


def test_collect_saved_skips_empty_and_keeps_message(tmp_path):
    outputs = [
        _Out("message", text="working"),
        _Out("result", data=[{"b64_json": ""}, {"b64_json": _b64()}]),
    ]
    saved, message = generate._collect_saved(outputs, n=5, out_dir=str(tmp_path))
    assert len(saved) == 1        # blank b64 skipped, real one saved
    assert message == "working"   # last message surfaced for error reporting
