"""Per-call choice of the ChatGPT chat model that drives image generation.

On the ChatGPT web path the image itself is drawn by a server-side image model we
cannot pick; what we choose is the chat model that orchestrates it ("upstream
model", e.g. gpt-5-5 or gpt-6). The vendored backend reads that name from
`config.default_upstream_model_name` (default gpt-5-5) inside
`OpenAIBackendAPI._image_model_settings`, for both image requests.
`use_upstream_model` overrides it for one call and restores it afterwards, so the
vendored files stay byte-identical. The override lives only in memory: vendored
`config.data` is written to disk solely by `_save`, which the image path never calls.

Which slugs an account may use comes from `GET /backend-api/models`
(`list_chat_models`); `newest_model` picks the highest plain `gpt-N[-M]` slug.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from typing import Iterator

import cgimg._vendor_path  # noqa: F401  (side effect: puts _vendor on sys.path)
from services.config import config

_KEY = "default_upstream_model_name"
_SLUG = re.compile(r"^[a-z0-9][a-z0-9.-]{0,63}$")
_PLAIN_GPT = re.compile(r"^gpt-(\d+)(?:-(\d+))?$")  # gpt-6, gpt-5-6 (no -mini etc.)
_MISSING = object()


def validate_model(model: str) -> str:
    """Return the slug unchanged if it looks like a model id, else raise ValueError."""
    if not _SLUG.match(model or ""):
        raise ValueError(f"invalid model slug {model!r} (expected e.g. gpt-6, gpt-5-5)")
    return model


@contextmanager
def use_upstream_model(model: str | None) -> Iterator[None]:
    """Route image requests inside the block through `model` (None = vendor default)."""
    if not model:
        yield
        return
    validate_model(model)
    prev = config.data.get(_KEY, _MISSING)
    config.data[_KEY] = model
    try:
        yield
    finally:
        if prev is _MISSING:
            config.data.pop(_KEY, None)
        else:
            config.data[_KEY] = prev


def newest_model(slugs: list[str]) -> str | None:
    """Highest plain gpt-N / gpt-N-M slug (gpt-6 > gpt-5-6 > gpt-5-5); None if none."""
    best: tuple[int, int] | None = None
    pick: str | None = None
    for s in slugs:
        m = _PLAIN_GPT.match(s)
        if not m:
            continue
        ver = (int(m.group(1)), int(m.group(2) or 0))
        if best is None or ver > best:
            best, pick = ver, s
    return pick


def list_chat_models(access_token: str) -> list[str]:
    """Model slugs this account may use (2 light backend calls: bootstrap + /models)."""
    from services.openai_backend_api import OpenAIBackendAPI

    with OpenAIBackendAPI(access_token=access_token) as api:
        return [m["id"] for m in api.list_models().get("data", [])]
