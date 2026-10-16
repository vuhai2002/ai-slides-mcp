"""Shared argparse options for the image-generating cgimg subcommands."""
from __future__ import annotations

import argparse
from typing import get_args

from cgimg.types import Thinking


def add_thinking_arg(p: argparse.ArgumentParser, default: str = "auto") -> None:
    """--thinking: image reasoning effort before drawing."""
    p.add_argument("--thinking", default=default, choices=list(get_args(Thinking)),
                   help=f"image reasoning effort (auto<standard<extended<max, default "
                        f"{default}); higher = better rendered text (e.g. VN diacritics)")


def add_model_arg(p: argparse.ArgumentParser) -> None:
    """--model: ChatGPT chat model that orchestrates the drawing (see `cgimg models`)."""
    p.add_argument("--model", default=None,
                   help="chat model that drives image generation, e.g. gpt-6 or gpt-5-6 "
                        "(default: gpt-5-5); list valid ones with `cgimg models`")


def add_brand_args(p: argparse.ArgumentParser) -> None:
    """--accent / --reserve-corner for slide-styling subcommands."""
    p.add_argument("--accent", default=None,
                   help="brand accent color hex, e.g. #10B981 (applied to bg/accents/text)")
    p.add_argument("--reserve-corner", dest="reserve_corner", default=None,
                   choices=["top-left", "top-right", "bottom-left", "bottom-right"],
                   help="keep this corner clear for a logo you add later; "
                        "the model draws no logo/text there")
