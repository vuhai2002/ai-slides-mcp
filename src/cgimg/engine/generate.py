"""Drive the vendored ChatGPT image-gen engine with our single-account token.

Entry: generate_image(prompt, aspect, n, out_dir) -> list of saved PNG paths.
"""
from __future__ import annotations

import base64
import os
import sys
import time

# Make the vendored `services.*` / `utils.*` importable; this also sets the
# vendored config's required auth-key env var (single source: see _vendor_path).
import cgimg._vendor_path  # noqa: F401  (side-effect: _vendor on sys.path + auth-key env)

from cgimg.sizes import resolve_size
from cgimg.types import RefMode, Style, Thinking

# Importing this wires the multi-account pool into the vendored shim AND forces
# sequential generation (side effects on import); it also exposes the pool
# accessors used here (get_pool) and re-exported for the deck layer
# (pool_exhausted_reset).
from cgimg.engine.account_wiring import get_pool, pool_exhausted_reset  # noqa: F401

from services.protocol.conversation import (  # noqa: E402
    ConversationRequest,
    encode_images,
    stream_image_outputs_with_pool,
)

from cgimg.engine.enhance import enhance_prompt, template_enhance  # noqa: E402
from cgimg.engine import image_thinking  # noqa: E402  (installs the thinking-effort patch)
from cgimg.engine.ref_modes import is_render_mode, ref_suffix  # noqa: E402

_SLIDE_STYLES = ("slide", "fintech")


def _collect_saved(outputs, n: int, out_dir: str) -> tuple[list[str], str]:
    """Save up to `n` images from the engine output stream.

    The backend can return MORE variants than requested (n=1 has been seen to
    yield 2 results); cap at `n` so callers get exactly what they asked for.
    Returns (saved_paths, last_message).
    """
    saved: list[str] = []
    message = ""
    for output in outputs:
        if output.kind == "message":
            message = output.text or message
        elif output.kind == "result":
            for item in output.data:
                if len(saved) >= n:
                    break
                b64 = str(item.get("b64_json") or "").strip()
                if not b64:
                    continue
                path = os.path.join(
                    out_dir, f"img-{int(time.time() * 1000)}-{len(saved)}.png"
                )
                with open(path, "wb") as f:
                    f.write(base64.b64decode(b64))
                saved.append(path)
        if len(saved) >= n:
            break
    return saved, message


def generate_image(
    prompt: str,
    aspect: str = "16:9",
    n: int = 1,
    out_dir: str = "out",
    enhance: bool = True,
    style: Style = "auto",
    ref_image: str | None = None,
    ref_mode: RefMode = "style",
    thinking: Thinking = "auto",
    brand_colors: list[str] | None = None,
    reserve_corner: str | None = None,
) -> list[str]:
    """Generate n image(s) and save them as PNGs. Returns saved file paths.

    When enhance is True (default), the prompt is first expanded via the ChatGPT
    text path (mirrors the web UI). style="slide" applies a clean editorial
    presentation-slide aesthetic (light, restrained, one hero, short labels) —
    best for slide content.

    When ref_image is a path, the engine attaches it so the model SEES it:
      ref_mode="style" (default) - match the reference's DESIGN STYLE only
        (palette, layout, typography, mood); its text/content is NOT copied.
      ref_mode="logo" (alias "asset") - the reference IS a real logo/brand asset;
        the model places it into the image exactly as given (no redraw/invent).
      ref_mode="render" (aliases "restyle", "architecture") - the reference is a
        3D render of a building; keep massing, openings and camera, change only
        materials, lighting and landscaping. All prompt rewriting (enhance and the
        offline slide template) is skipped, since it would turn it into a slide.

    thinking selects reasoning effort before drawing: "auto" (default = ChatGPT's
    own default) or "standard"/"extended"/"max" (increasing). Higher effort
    improves rendered-text fidelity (e.g. Vietnamese diacritics) at the cost of
    speed.

    brand_colors (list of hex) forces a palette; reserve_corner (e.g. "top-left")
    keeps a corner clear for a logo and bans any model-drawn logo/text. With
    enhance=False, supplying a slide style / brand_colors / reserve_corner routes
    through the deterministic offline template (concise, no LLM bloat) instead of
    being silently ignored.
    """
    size = resolve_size(aspect)
    render = bool(ref_image) and is_render_mode(ref_mode)
    if render:
        print("[render] restyling a building render; prompt sent verbatim", file=sys.stderr)
    elif enhance:
        # Fix the account for THIS slide so enhance (text) and the image share it
        # (raises NoQuotaError up-front if every account is exhausted).
        active = get_pool().current_token()
        prompt = enhance_prompt(prompt, style=style, brand_colors=brand_colors,
                                reserve_corner=reserve_corner, access_token=active)
        print(f"[enhance] prompt expanded to {len(prompt)} chars", file=sys.stderr)
    elif style in _SLIDE_STYLES or brand_colors or reserve_corner:
        prompt = template_enhance(prompt, style=style, brand_colors=brand_colors,
                                  reserve_corner=reserve_corner)
        print(f"[template] styled prompt ({len(prompt)} chars, no LLM)", file=sys.stderr)

    encoded: list[str] | None = None
    if ref_image:
        prompt = prompt + ref_suffix(ref_mode)
        ext = os.path.splitext(ref_image)[1].lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        with open(ref_image, "rb") as f:
            data = f.read()
        encoded = encode_images([(data, mime, os.path.basename(ref_image))])

    request = ConversationRequest(
        model="gpt-image-2",
        prompt=prompt,
        size=size,
        n=n,
        quality="auto",
        images=encoded,
        # response_format defaults to "b64_json" -> result dicts carry b64_json.
    )

    os.makedirs(out_dir, exist_ok=True)

    # Select reasoning effort for the image-prepare payload (no-op when "auto").
    image_thinking.set_thinking(thinking)
    try:
        # The pool wrapper calls account_service.get_available_access_token()
        # internally (our shim -> our token), so no manual backend construction.
        saved, message = _collect_saved(
            stream_image_outputs_with_pool(request), n, out_dir
        )
    finally:
        image_thinking.set_thinking("auto")

    if not saved:
        raise RuntimeError(
            f"image generation produced no images. Engine said: {message or '(no message)'}"
        )
    return saved
