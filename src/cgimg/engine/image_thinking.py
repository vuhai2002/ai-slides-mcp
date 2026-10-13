"""Per-request `thinking_effort` for image generation.

The ChatGPT web UI has an "Intelligence" selector that makes the image model
reason more before drawing. More reasoning improves fine detail and especially
TEXT rendering (e.g. Vietnamese diacritics), at the cost of speed.

The vendored backend picks `(upstream_model, thinking_effort)` for an image
request in ONE place, `OpenAIBackendAPI._image_model_settings`, and puts that
effort on BOTH image requests (the `/f/conversation/prepare` POST and the main
`/f/conversation` POST). Upstream only reads it from a global config value; we
wrap that method so a per-call level (set_thinking) wins, WITHOUT editing the
vendored file - scripts/update-vendor.sh can still re-pull it verbatim.
tests/test_image_thinking.py fails loudly if upstream drops or bypasses the hook.

Valid wire values (reverse-engineered; anything else -> HTTP 422 "Invalid
conversation body"): "standard" < "extended" < "max", roughly the web UI's
Instant/Medium/High. "auto"/None leaves upstream's own default (no field).
"""
from __future__ import annotations

import cgimg._vendor_path  # noqa: F401  (side effect: puts _vendor on sys.path)
from services.openai_backend_api import OpenAIBackendAPI

_VALID = {"standard", "extended", "max"}
_level: str | None = None


def set_thinking(level: str | None) -> None:
    """Select reasoning effort for subsequent image generations.

    level: "auto" / None (default - send nothing; ChatGPT's own default), or one
    of "standard", "extended", "max" (increasing reasoning). Higher = better
    rendered text but slower. Raises ValueError on anything else.
    """
    global _level
    norm = (level or "auto").strip().lower()
    if norm in ("auto", ""):
        _level = None
        return
    if norm not in _VALID:
        raise ValueError(
            f"unknown thinking level {level!r}; use auto|standard|extended|max"
        )
    _level = norm


def current() -> str | None:
    return _level


_orig_settings = OpenAIBackendAPI._image_model_settings


def _image_model_settings(self, model):
    upstream_model, effort = _orig_settings(self, model)
    if _level is None:
        return upstream_model, effort
    return upstream_model, _level


# Install once (idempotent across re-imports).
if not getattr(OpenAIBackendAPI._image_model_settings, "_cgimg_thinking", False):
    _image_model_settings._cgimg_thinking = True
    OpenAIBackendAPI._image_model_settings = _image_model_settings
