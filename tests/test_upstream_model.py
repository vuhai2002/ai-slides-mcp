"""Offline tests for the per-call upstream chat model (`model` / `--model`)."""
import asyncio
import base64
import inspect

import pytest

from cgimg import cli, server
from cgimg.engine import generate
from cgimg.engine.upstream_model import newest_model, use_upstream_model, validate_model
from services.config import config

KEY = "default_upstream_model_name"


def test_override_applies_inside_block_and_restores_missing_key():
    config.data.pop(KEY, None)
    with use_upstream_model("gpt-6"):
        assert config.default_upstream_model_name == "gpt-6"
    assert KEY not in config.data
    assert config.default_upstream_model_name == "gpt-5-5"  # vendor default again


def test_override_restores_previous_value_even_on_error():
    config.data[KEY] = "gpt-5-6"
    try:
        with pytest.raises(RuntimeError):
            with use_upstream_model("gpt-6"):
                raise RuntimeError("boom")
        assert config.data[KEY] == "gpt-5-6"
    finally:
        config.data.pop(KEY, None)


def test_none_is_a_no_op():
    config.data.pop(KEY, None)
    with use_upstream_model(None):
        assert KEY not in config.data


@pytest.mark.parametrize("bad", ["", "GPT 6", "gpt-6; rm -rf", "../x"])
def test_invalid_slug_rejected(bad):
    with pytest.raises(ValueError):
        validate_model(bad)


def test_newest_model_picks_highest_plain_gpt():
    live = ["auto", "gpt-5-3-mini", "gpt-5-5", "gpt-5-5-mini", "gpt-5-6", "gpt-5-6-mini",
            "gpt-5-6-t-mini", "gpt-6", "gpt-6-mini", "gpt-6-t-mini", "research"]
    assert newest_model(live) == "gpt-6"
    assert newest_model(["gpt-5-5", "gpt-5-6"]) == "gpt-5-6"
    assert newest_model(["auto", "research", "gpt-6-mini"]) is None


class _Out:
    def __init__(self):
        self.kind = "result"
        self.data = [{"b64_json": base64.b64encode(b"\x89PNGfake").decode()}]
        self.text = None


def test_generate_image_uses_model_only_during_the_request(monkeypatch, tmp_path):
    seen = {}

    def stream(request):
        seen["model"] = config.default_upstream_model_name
        return [_Out()]

    monkeypatch.setattr(generate, "stream_image_outputs_with_pool", stream)
    config.data.pop(KEY, None)
    generate.generate_image("x", out_dir=str(tmp_path), enhance=False, model="gpt-6")
    assert seen["model"] == "gpt-6"
    assert config.default_upstream_model_name == "gpt-5-5"
    generate.generate_image("x", out_dir=str(tmp_path), enhance=False)
    assert seen["model"] == "gpt-5-5"


@pytest.mark.parametrize("argv,target,attr", [
    (["gen", "p", "--model", "gpt-6", "--no-enhance"], "cgimg.engine.generate", "generate_image"),
    (["deck", "--prompts", "a", "--model", "gpt-6"], "cgimg.engine.decks", "build_slide_deck"),
    (["branded", "logo.png", "--prompts", "a", "--model", "gpt-6"], "cgimg.branding.deck", "branded_deck"),
    (["styled", "ref.png", "--prompts", "a", "--model", "gpt-6"], "cgimg.branding.deck", "styled_deck"),
])
def test_cli_forwards_model(monkeypatch, argv, target, attr):
    import importlib
    seen = {}
    mod = importlib.import_module(target)

    def fake(*a, **kw):
        seen.update(kw)
        return [] if attr == "generate_image" else {"path": "d", "image_paths": []}

    monkeypatch.setattr(mod, attr, fake)
    assert cli.main(argv) == 0
    assert seen["model"] == "gpt-6"


def test_deck_forwards_model_per_slide(monkeypatch, tmp_path):
    import cgimg.engine.decks as decks
    seen = []
    img = tmp_path / "x.png"
    img.write_bytes(b"png")
    monkeypatch.setattr(decks, "generate_image", lambda p, **kw: seen.append(kw["model"]) or [str(img)])
    monkeypatch.setattr(decks, "build_pptx", lambda imgs, outp, aspect: str(outp))
    decks.build_slide_deck(["a"], out_dir=str(tmp_path), out_pptx=str(tmp_path / "d.pptx"),
                           model="gpt-6")
    assert seen == ["gpt-6"]


def test_mcp_tools_accept_model_and_list_models_exists():
    for fn in (server.generate_image, server.generate_slide_deck,
               server.branded_deck, server.styled_deck):
        fn = getattr(fn, "fn", fn)
        assert inspect.signature(fn).parameters["model"].default is None
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert "list_models" in names
