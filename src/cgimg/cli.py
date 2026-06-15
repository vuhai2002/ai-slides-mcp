"""cgimg CLI: login / gen / deck / ppt / branded / styled."""
from __future__ import annotations
import argparse
import sys
from typing import get_args

from cgimg.types import Style, Thinking


def _add_thinking_arg(p: argparse.ArgumentParser) -> None:
    """Shared --thinking option for image-generating subcommands."""
    p.add_argument("--thinking", default="auto", choices=list(get_args(Thinking)),
                   help="image reasoning effort (auto<standard<extended<max); higher "
                        "= better rendered text (e.g. VN diacritics) but slower")


def _add_brand_args(p: argparse.ArgumentParser) -> None:
    """Shared --accent / --reserve-corner options for slide-styling subcommands."""
    p.add_argument("--accent", default=None,
                   help="brand accent color hex, e.g. #10B981 (applied to bg/accents/text)")
    p.add_argument("--reserve-corner", dest="reserve_corner", default=None,
                   choices=["top-left", "top-right", "bottom-left", "bottom-right"],
                   help="keep this corner clear for a logo you add later; "
                        "the model draws no logo/text there")


def _cmd_login(args: argparse.Namespace) -> int:
    from cgimg.auth import oauth_login, tokens
    if args.callback:
        oauth_login.complete(args.callback)
        print(f"[OK] Logged in. Saved to {tokens._auth_path()}")
        return 0
    url = oauth_login.build_and_stash(args.email or "")
    print("\n1. A browser should have opened. If not, open this URL:\n")
    print("   " + url + "\n")
    print("2. Log into ChatGPT. You'll land on a platform.openai.com page (may say 'Oops').")
    print("3. Copy the FULL URL from the address bar, then run:\n")
    print('   cgimg login --callback "<paste the URL here>"\n')
    return 0


def _cmd_gen(args: argparse.Namespace) -> int:
    from cgimg.engine.generate import generate_image
    brand_colors = [args.accent] if args.accent else None
    paths = generate_image(args.prompt, aspect=args.aspect, n=args.n,
                           out_dir=args.out, enhance=args.enhance, style=args.style,
                           thinking=args.thinking, brand_colors=brand_colors,
                           reserve_corner=args.reserve_corner)
    for p in paths:
        print(p)
    return 0


def _load_prompts(args: argparse.Namespace) -> list[str]:
    """Prompts from --prompts (args) or --prompts-file (one/line, skip blank + '#')."""
    if args.prompts_file:
        with open(args.prompts_file, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f]
        prompts = [ln for ln in lines if ln and not ln.startswith("#")]
    else:
        prompts = list(args.prompts or [])
    if not prompts:
        raise SystemExit("no prompts: pass --prompts ... or --prompts-file <path>")
    return prompts


def _cmd_deck(args: argparse.Namespace) -> int:
    from cgimg.engine.decks import build_slide_deck
    brand_colors = [args.accent] if args.accent else None
    result = build_slide_deck(_load_prompts(args), aspect=args.aspect, out_pptx=args.out,
                              out_dir=args.out_dir, enhance=args.enhance, style=args.style,
                              brand_colors=brand_colors, reserve_corner=args.reserve_corner,
                              thinking=args.thinking)
    print(f"deck: {result['path']}")
    for p in result["image_paths"]:
        print(p)
    return 0


def _cmd_ppt(args: argparse.Namespace) -> int:
    from cgimg.ppt.builder import build_pptx
    print(build_pptx(args.images, args.out, aspect=args.aspect))
    return 0


def _cmd_branded(args: argparse.Namespace) -> int:
    from cgimg.branding.deck import branded_deck
    result = branded_deck(args.logo_path, args.prompts, aspect=args.aspect,
                          out_pptx=args.out, out_dir=args.out_dir,
                          logo_position=args.position, logo_scale=args.scale,
                          thinking=args.thinking)
    print(f"deck: {result['path']}")
    print(f"brand_colors: {', '.join(result['brand_colors'])}")
    for p in result["image_paths"]:
        print(p)
    return 0


def _cmd_styled(args: argparse.Namespace) -> int:
    from cgimg.branding.deck import styled_deck
    result = styled_deck(args.ref_image, args.prompts, aspect=args.aspect,
                         out_pptx=args.out, out_dir=args.out_dir,
                         thinking=args.thinking)
    print(f"deck: {result['path']}")
    print(f"brand_colors: {', '.join(result['brand_colors'])}")
    for p in result["image_paths"]:
        print(p)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cgimg")
    sub = p.add_subparsers(dest="cmd", required=True)

    lg = sub.add_parser("login")
    lg.add_argument("--callback", default=None, help="callback URL or code (step 2)")
    lg.add_argument("--email", default=None, help="optional email hint")
    lg.set_defaults(func=_cmd_login)

    g = sub.add_parser("gen")
    g.add_argument("prompt")
    g.add_argument("--aspect", default="16:9")
    g.add_argument("--n", type=int, default=1)
    g.add_argument("--out", default="out")
    g.add_argument("--no-enhance", dest="enhance", action="store_false",
                   help="skip auto-expanding the prompt via the ChatGPT text path")
    g.add_argument("--style", default="auto", choices=list(get_args(Style)),
                   help="'slide' = clean editorial; 'fintech' = light-blue dashboard")
    _add_thinking_arg(g)
    _add_brand_args(g)
    g.set_defaults(func=_cmd_gen, enhance=True)

    pp = sub.add_parser("ppt")
    pp.add_argument("images", nargs="+")
    pp.add_argument("--out", default="deck.pptx")
    pp.add_argument("--aspect", default="16:9")
    pp.set_defaults(func=_cmd_ppt)

    br = sub.add_parser("branded")
    br.add_argument("logo_path")
    br.add_argument("--prompts", nargs="+", required=True)
    br.add_argument("--out", default="deck.pptx")
    br.add_argument("--out-dir", dest="out_dir", default="out")
    br.add_argument("--aspect", default="16:9")
    br.add_argument("--position", default="top-left")
    br.add_argument("--scale", type=float, default=0.15)
    _add_thinking_arg(br)
    br.set_defaults(func=_cmd_branded)

    st = sub.add_parser("styled")
    st.add_argument("ref_image")
    st.add_argument("--prompts", nargs="+", required=True)
    st.add_argument("--out", default="deck.pptx")
    st.add_argument("--out-dir", dest="out_dir", default="out")
    st.add_argument("--aspect", default="16:9")
    _add_thinking_arg(st)
    st.set_defaults(func=_cmd_styled)

    dk = sub.add_parser("deck", help="generate a multi-slide PPTX (one image per prompt)")
    grp = dk.add_mutually_exclusive_group(required=True)
    grp.add_argument("--prompts", nargs="+", help="slide contents, one per arg")
    grp.add_argument("--prompts-file", dest="prompts_file",
                     help="file with one prompt per line (blank lines and # comments skipped)")
    dk.add_argument("--out", default="deck.pptx")
    dk.add_argument("--out-dir", dest="out_dir", default="out")
    dk.add_argument("--aspect", default="16:9")
    dk.add_argument("--no-enhance", dest="enhance", action="store_false",
                    help="skip the LLM enhance; a --style still applies via offline template")
    dk.add_argument("--style", default="slide", choices=list(get_args(Style)))
    _add_thinking_arg(dk)
    _add_brand_args(dk)
    dk.set_defaults(func=_cmd_deck, enhance=True)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
