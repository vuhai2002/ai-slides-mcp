"""Assemble a plain multi-slide PPTX: one generated image per prompt.

The non-branded counterpart of branding/deck.py. Shared by the MCP
`generate_slide_deck` tool and the CLI `deck` command (single source of truth).

When the account pool runs out of image quota mid-deck, generation STOPS and the
PPTX is assembled from the slides finished so far (decision #6): the result is
marked `incomplete` with how many slides were done and when quota resets. A
non-quota failure (e.g. content policy) still raises, as before.
"""
from __future__ import annotations

import os
import sys

from cgimg.engine.generate import generate_image, pool_exhausted_reset
from cgimg.ppt.builder import build_pptx
from cgimg.types import Style, Thinking


def finish_deck(images: list[str], out_pptx: str, aspect: str, total: int,
                reset_at: str | None, extra: dict | None = None) -> dict:
    """Assemble the PPTX from produced slides and build the (additive) result dict.

    Writes NO file when zero slides were produced (path=None). Always returns
    `incomplete/generated/total/reset_at` so a fully-successful deck reports
    incomplete=False, generated==total, reset_at=None.
    """
    deck = build_pptx(images, out_pptx, aspect=aspect) if images else None
    result = {
        "path": deck,
        "image_paths": images,
        "incomplete": len(images) < total,
        "generated": len(images),
        "total": total,
        "reset_at": reset_at,
    }
    if extra:
        result.update(extra)
    return result


def build_slide_deck(
    prompts: list[str],
    *,
    aspect: str = "16:9",
    out_pptx: str = "deck.pptx",
    out_dir: str = "out",
    enhance: bool = True,
    style: Style = "slide",
    brand_colors: list[str] | None = None,
    reserve_corner: str | None = None,
    thinking: Thinking = "auto",
    name_prefix: str = "s",
) -> dict:
    """Generate one image per prompt, name them `<prefix>NN.png`, assemble a PPTX.

    Returns {path, image_paths, incomplete, generated, total, reset_at}. Each
    prompt is the content of one slide. See generate_image for the meaning of
    style / brand_colors / reserve_corner / thinking (all forwarded per slide).
    """
    if not prompts:
        raise ValueError("no prompts provided")
    os.makedirs(out_dir, exist_ok=True)

    images: list[str] = []
    total = len(prompts)
    reset_at: str | None = None
    for i, prompt in enumerate(prompts, 1):
        print(f"[slide_deck] slide {i}/{total}", file=sys.stderr)
        try:
            paths = generate_image(
                prompt, aspect=aspect, n=1, out_dir=out_dir, enhance=enhance, style=style,
                brand_colors=brand_colors, reserve_corner=reserve_corner, thinking=thinking,
            )
        except Exception:
            exhausted, reset_at = pool_exhausted_reset()
            if exhausted:
                print(f"[slide_deck] hết quota ảnh tại slide {i}/{total}; dừng lại.",
                      file=sys.stderr)
                break
            raise  # non-quota failure -> unchanged behaviour
        # Rename the auto-named output to a stable, ordered slide name.
        dst = os.path.join(out_dir, f"{name_prefix}{i:02d}.png")
        src = paths[0]
        if os.path.abspath(src) != os.path.abspath(dst):
            os.replace(src, dst)
        images.append(dst)

    return finish_deck(images, out_pptx, aspect, total, reset_at)
