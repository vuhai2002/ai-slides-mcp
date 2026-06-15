"""FastMCP stdio server exposing cgimg tools."""
from __future__ import annotations
from mcp.server.fastmcp import FastMCP

from cgimg.types import Style, Thinking

mcp = FastMCP("ai-slides")


@mcp.tool()
def login_status() -> dict:
    """Check logged-in ChatGPT accounts. Cheap + hint-based (no network probe):
    returns {authed, accounts:[{email, type, alive, restore_at}], ready_count}.
    ready_count is from persisted hints; for live quota run the CLI `cgimg accounts`."""
    from cgimg.auth.pool import AccountPool
    rows = AccountPool().status()  # hints only, no network
    return {
        "authed": len(rows) > 0,
        "accounts": [{"email": r["email"], "type": r["type"],
                      "alive": r["alive"], "restore_at": r["restore_at"]} for r in rows],
        "ready_count": sum(1 for r in rows if r["alive"]),
    }


@mcp.tool()
def generate_image(prompt: str, aspect: str = "16:9", n: int = 1,
                   out_dir: str = "out", enhance: bool = True,
                   style: Style = "auto", thinking: Thinking = "auto",
                   brand_colors: list[str] | None = None,
                   reserve_corner: str | None = None) -> dict:
    """Generate image(s) from a text prompt at the given aspect ratio
    (16:9, 1:1, 3:4, 4:3, 9:16, or WxH). Returns saved PNG file paths.

    When enhance is True (default), the prompt is auto-expanded via the ChatGPT
    text path before drawing. style='slide' = clean editorial slide (light cream,
    one accent, hero visual); style='fintech' = premium light-blue dashboard look
    (glass cards, blue icon badges, optional robot + charts). Both auto-complete
    content into a full, information-rich slide (label + 2-line description per
    point, sparse input expanded). style='auto' is the general default.

    thinking sets reasoning effort before drawing: 'auto' (ChatGPT default) or
    'standard'/'extended'/'max' (increasing). Higher effort improves rendered-text
    fidelity (e.g. Vietnamese diacritics) at the cost of speed.

    brand_colors (list of hex like ['#10B981']) forces a palette; reserve_corner
    (e.g. 'top-left') keeps a corner clear for a logo and bans model-drawn
    logos/text. With enhance=False these still apply via the offline template."""
    from cgimg.engine.generate import generate_image as _gen
    return {"paths": _gen(prompt, aspect=aspect, n=n, out_dir=out_dir,
                          enhance=enhance, style=style, thinking=thinking,
                          brand_colors=brand_colors, reserve_corner=reserve_corner)}


@mcp.tool()
def build_pptx(image_paths: list[str], out_path: str = "deck.pptx",
               aspect: str = "16:9") -> dict:
    """Assemble existing image files into a full-bleed PowerPoint deck."""
    from cgimg.ppt.builder import build_pptx as _build
    return {"path": _build(image_paths, out_path, aspect=aspect)}


@mcp.tool()
def generate_slide_deck(prompts: list[str], aspect: str = "16:9",
                        out_pptx: str = "deck.pptx", out_dir: str = "out",
                        enhance: bool = True, style: Style = "slide",
                        thinking: Thinking = "auto",
                        brand_colors: list[str] | None = None,
                        reserve_corner: str | None = None) -> dict:
    """Generate one image per prompt then assemble them into a PPTX deck.

    Each prompt should be the CONTENT of one slide. style='slide' (default here)
    applies a clean editorial presentation design (light, restrained accent, one
    hero visual, short labels, takeaway banner) — pass raw slide content and the
    enhancer designs it. Set enhance=False to send prompts verbatim (a slide style
    or brand_colors/reserve_corner still apply via the offline template).

    thinking ('auto'/'standard'/'extended'/'max') sets image reasoning effort;
    higher renders Vietnamese text more reliably but is slower. brand_colors +
    reserve_corner work as in generate_image. Slides are named s01.png, s02.png...

    If every logged-in account runs out of image quota mid-deck, generation stops
    and a PARTIAL deck is returned: the result carries incomplete=True, generated,
    total, and reset_at (when quota next resets). Re-run later to make the rest."""
    from cgimg.engine.decks import build_slide_deck
    return build_slide_deck(prompts, aspect=aspect, out_pptx=out_pptx, out_dir=out_dir,
                            enhance=enhance, style=style, brand_colors=brand_colors,
                            reserve_corner=reserve_corner, thinking=thinking)


@mcp.tool()
def branded_deck(logo_path: str, prompts: list[str], aspect: str = "16:9",
                 out_pptx: str = "deck.pptx", out_dir: str = "out",
                 logo_position: str = "top-left", logo_scale: float = 0.15,
                 thinking: Thinking = "auto") -> dict:
    """Build a branded slide deck: auto-detect brand colors from the logo, generate
    slides in those colors, composite the original logo onto each slide, assemble PPTX.

    thinking ('auto'/'standard'/'extended'/'max') sets image reasoning effort;
    higher renders Vietnamese text more reliably but is slower."""
    from cgimg.branding.deck import branded_deck as _bd
    return _bd(logo_path, prompts, aspect=aspect, out_pptx=out_pptx, out_dir=out_dir,
               logo_position=logo_position, logo_scale=logo_scale, thinking=thinking)


@mcp.tool()
def styled_deck(ref_image: str, prompts: list[str], aspect: str = "16:9",
                out_pptx: str = "deck.pptx", out_dir: str = "out",
                thinking: Thinking = "auto") -> dict:
    """Generate a deck matching a reference design image's style and colors (content not copied).

    thinking ('auto'/'standard'/'extended'/'max') sets image reasoning effort;
    higher renders Vietnamese text more reliably but is slower."""
    from cgimg.branding.deck import styled_deck as _sd
    return _sd(ref_image, prompts, aspect=aspect, out_pptx=out_pptx, out_dir=out_dir,
               thinking=thinking)


def main() -> None:
    from cgimg.console import force_utf8
    force_utf8()  # UTF-8 stderr so non-ASCII progress lines / paths never crash a cp1252 console
    mcp.run()


if __name__ == "__main__":
    main()
