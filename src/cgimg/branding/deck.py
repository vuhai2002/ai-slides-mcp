"""Orchestrate a branded slide deck: detect brand colors from a logo, generate
slides in those colors, composite the original logo onto each, assemble a PPTX.

Reuses the existing engine (generate_image, enhance_prompt) and ppt builder -
this module only wires them together. When the account pool runs out of image
quota mid-deck, generation stops and the PPTX is assembled from the slides
finished so far (decision #6): the result is marked `incomplete` with the
soonest quota reset.
"""
from __future__ import annotations

import os
import sys

from cgimg.branding.colors import extract_brand_colors
from cgimg.branding.composite import overlay_logo
from cgimg.engine.decks import finish_deck
from cgimg.engine.enhance import enhance_prompt
from cgimg.engine.generate import generate_image, pool_exhausted_reset
from cgimg.types import Thinking


def branded_deck(logo_path: str, prompts: list[str], aspect: str = "16:9",
                 out_pptx: str = "deck.pptx", out_dir: str = "out",
                 logo_position: str = "top-left", logo_scale: float = 0.15,
                 thinking: Thinking = "auto") -> dict:
    """Build a branded deck and return its path, slide images, brand colors, and
    partial-deck status (incomplete/generated/total/reset_at).

    thinking ("auto"/"standard"/"extended"/"max") sets the image reasoning effort;
    higher renders Vietnamese text more reliably but is slower.
    """
    if not prompts:
        raise ValueError("no prompts provided")

    colors = extract_brand_colors(logo_path)
    os.makedirs(out_dir, exist_ok=True)

    composited: list[str] = []
    total = len(prompts)
    reset_at: str | None = None
    for i, prompt in enumerate(prompts):
        print(f"[branded_deck] slide {i + 1}/{total}", file=sys.stderr)
        # Inject brand context, then generate verbatim (already enhanced).
        enhanced = enhance_prompt(prompt, brand_colors=colors, reserve_corner=logo_position)
        try:
            imgs = generate_image(enhanced, aspect=aspect, n=1, out_dir=out_dir,
                                  enhance=False, thinking=thinking)
        except Exception:
            exhausted, reset_at = pool_exhausted_reset()
            if exhausted:
                print(f"[branded_deck] out of image quota at slide {i + 1}/{total}; stopping.",
                      file=sys.stderr)
                break
            raise  # non-quota failure -> unchanged behaviour
        out_png = os.path.join(out_dir, f"branded-{i}.png")
        overlay_logo(imgs[0], logo_path, out_png,
                     position=logo_position, scale=logo_scale)
        composited.append(out_png)

    return finish_deck(composited, out_pptx, aspect, total, reset_at,
                       extra={"brand_colors": colors})


def styled_deck(ref_image: str, prompts: list[str], aspect: str = "16:9",
                out_pptx: str = "deck.pptx", out_dir: str = "out",
                thinking: Thinking = "auto") -> dict:
    """Generate a slide deck whose design MATCHES a reference image (style + colors).

    - extract brand colors from ref_image
    - for each prompt: enhance (style='slide' + brand_colors) then generate with the
      ref_image attached as a STYLE reference (content NOT copied)
    - assemble PPTX. Returns {path, image_paths, brand_colors, incomplete,
      generated, total, reset_at}.

    A failing slide is retried up to 3 times (ChatGPT sometimes throws a transient
    content-policy/timeout error that clears on re-run), then skipped. But if the
    pool is out of quota, the whole deck stops immediately (no point retrying) and
    returns a partial, incomplete result.
    """
    if not prompts:
        raise ValueError("no prompts provided")

    colors = extract_brand_colors(ref_image)
    os.makedirs(out_dir, exist_ok=True)

    images: list[str] = []
    skipped: list[int] = []
    total = len(prompts)
    reset_at: str | None = None
    exhausted = False
    for i, prompt in enumerate(prompts):
        if exhausted:
            break
        enhanced = enhance_prompt(prompt, style="slide", brand_colors=colors)
        img: str | None = None
        for attempt in range(1, 4):
            try:
                imgs = generate_image(enhanced, aspect=aspect, n=1, out_dir=out_dir,
                                      enhance=False, ref_image=ref_image, thinking=thinking)
                img = imgs[0]
                break
            except Exception as exc:
                exhausted, reset_at = pool_exhausted_reset()
                if exhausted:
                    print(f"[styled_deck] out of image quota at slide {i + 1}; stopping.",
                          file=sys.stderr)
                    break
                print(f"[styled_deck] slide {i + 1} attempt {attempt} failed: {exc}",
                      file=sys.stderr)
        if img:
            images.append(img)
        elif not exhausted:
            skipped.append(i + 1)
            print(f"[styled_deck] slide {i + 1} skipped after 3 attempts", file=sys.stderr)

    # Genuine all-failed (not quota) keeps the old hard error; quota -> partial.
    if not images and not exhausted:
        raise RuntimeError("no slides could be generated")
    if skipped:
        print(f"[styled_deck] skipped slides: {skipped}", file=sys.stderr)

    return finish_deck(images, out_pptx, aspect, total, reset_at,
                       extra={"brand_colors": colors})
