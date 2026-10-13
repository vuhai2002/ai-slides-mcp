"""Offline tests for reference-image modes (style / logo / render)."""
import base64

import pytest

from cgimg.engine import generate
from cgimg.engine.ref_modes import is_render_mode, ref_suffix


def test_style_suffix_says_do_not_copy():
    style = ref_suffix("style")
    assert "PHONG CÁCH" in style and "KHÔNG sao chép" in style


def test_logo_suffix_says_keep_logo_exact():
    logo = ref_suffix("logo")
    assert "LOGO" in logo and "CHÍNH XÁC" in logo
    assert ref_suffix("asset") == logo  # alias


def test_render_suffix_keeps_architecture():
    render = ref_suffix("render")
    assert "GIỮ NGUYÊN kiến trúc" in render
    assert "Keep the architecture EXACTLY" in render
    assert ref_suffix("restyle") == render  # alias
    assert ref_suffix("architecture") == render  # alias


def test_modes_give_distinct_instructions():
    assert len({ref_suffix("style"), ref_suffix("logo"), ref_suffix("render")}) == 3


def test_is_render_mode():
    assert all(is_render_mode(m) for m in ("render", "restyle", "architecture"))
    assert not any(is_render_mode(m) for m in ("style", "logo", "asset"))


class _Out:
    """Minimal stand-in for the vendored ImageOutput."""

    def __init__(self):
        self.kind = "result"
        self.data = [{"b64_json": base64.b64encode(b"\x89PNGfake").decode()}]
        self.text = None


@pytest.fixture
def engine(monkeypatch, tmp_path):
    """Stub the network: capture the final request and record any prompt rewrite."""
    calls = {"rewrites": [], "request": None}

    def _stream(request):
        calls["request"] = request
        return [_Out()]

    monkeypatch.setattr(generate, "stream_image_outputs_with_pool", _stream)
    monkeypatch.setattr(generate, "enhance_prompt",
                        lambda p, **kw: calls["rewrites"].append("enhance") or "ENHANCED")
    monkeypatch.setattr(generate, "template_enhance",
                        lambda p, **kw: calls["rewrites"].append("template") or "TEMPLATED")
    monkeypatch.setattr(generate, "get_pool",
                        lambda: type("P", (), {"current_token": lambda self: "tok"})())
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"\x89PNGref")
    calls["ref"] = str(ref)
    calls["out"] = str(tmp_path / "out")
    return calls


def test_render_mode_sends_prompt_verbatim(engine):
    generate.generate_image("Indochine, warm light", out_dir=engine["out"], enhance=True,
                            style="slide", brand_colors=["#10B981"],
                            ref_image=engine["ref"], ref_mode="render")
    assert engine["rewrites"] == []  # neither enhance nor the slide template ran
    prompt = engine["request"].prompt
    assert prompt.startswith("Indochine, warm light")
    assert prompt.endswith(ref_suffix("render"))
    assert engine["request"].images  # the render is attached


def test_logo_mode_still_enhances(engine):
    generate.generate_image("launch poster", out_dir=engine["out"],
                            ref_image=engine["ref"], ref_mode="logo")
    assert engine["rewrites"] == ["enhance"]
    assert engine["request"].prompt == "ENHANCED" + ref_suffix("logo")


def test_render_mode_without_ref_image_is_ignored(engine):
    generate.generate_image("plain", out_dir=engine["out"], ref_mode="render")
    assert engine["rewrites"] == ["enhance"]
    assert engine["request"].images is None
