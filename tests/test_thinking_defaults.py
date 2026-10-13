"""Deck tools default to thinking="max"; single-image generation keeps "auto"."""
import inspect

import pytest

from cgimg import cli, server
from cgimg.branding import deck
from cgimg.engine import decks


def _default(fn) -> str:
    fn = getattr(fn, "fn", fn)  # unwrap a FastMCP tool if needed
    return inspect.signature(fn).parameters["thinking"].default


@pytest.mark.parametrize("fn", [server.generate_slide_deck, server.branded_deck,
                                server.styled_deck, decks.build_slide_deck,
                                deck.branded_deck, deck.styled_deck])
def test_deck_paths_default_to_max(fn):
    assert _default(fn) == "max"


@pytest.mark.parametrize("fn", [server.generate_image])
def test_single_image_defaults_to_auto(fn):
    assert _default(fn) == "auto"


@pytest.mark.parametrize("argv,expected", [
    (["deck", "--prompts", "a"], "max"),
    (["branded", "logo.png", "--prompts", "a"], "max"),
    (["styled", "ref.png", "--prompts", "a"], "max"),
    (["gen", "a"], "auto"),
])
def test_cli_thinking_defaults(monkeypatch, argv, expected):
    seen = {}

    def _capture(parser_self, args=None, namespace=None):
        ns = _orig_parse(parser_self, args, namespace)
        seen["thinking"] = ns.thinking
        raise SystemExit(0)  # stop before any generation runs

    import argparse
    _orig_parse = argparse.ArgumentParser.parse_args
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", _capture)
    with pytest.raises(SystemExit):
        cli.main(argv)
    assert seen["thinking"] == expected
