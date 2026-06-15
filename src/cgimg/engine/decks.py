"""Assemble a plain multi-slide PPTX: one generated image per prompt.

The non-branded counterpart of branding/deck.py. Shared by the MCP
`generate_slide_deck` tool and the CLI `deck` command (single source of truth).
"""
from __future__ import annotations

import os
import sys

from cgimg.engine.generate import generate_image
from cgimg.ppt.builder import build_pptx
from cgimg.types import Style, Thinking


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

    Returns {path, image_paths}. Each prompt is the content of one slide. See
    generate_image for the meaning of style / brand_colors / reserve_corner /
    thinking (all forwarded per slide).
    """
    if not prompts:
        raise ValueError("no prompts provided")
    os.makedirs(out_dir, exist_ok=True)

    images: list[str] = []
    total = len(prompts)
    for i, prompt in enumerate(prompts, 1):
        print(f"[slide_deck] slide {i}/{total}", file=sys.stderr)
        paths = generate_image(
            prompt, aspect=aspect, n=1, out_dir=out_dir, enhance=enhance, style=style,
            brand_colors=brand_colors, reserve_corner=reserve_corner, thinking=thinking,
        )
        # Rename the auto-named output to a stable, ordered slide name.
        dst = os.path.join(out_dir, f"{name_prefix}{i:02d}.png")
        src = paths[0]
        if os.path.abspath(src) != os.path.abspath(dst):
            os.replace(src, dst)
        images.append(dst)

    deck = build_pptx(images, out_pptx, aspect=aspect)
    return {"path": deck, "image_paths": images}
