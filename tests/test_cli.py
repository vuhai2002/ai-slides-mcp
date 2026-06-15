"""CLI tests for the `deck` command and shared brand args (issues #1, #3, #4)."""
from cgimg import cli


def test_deck_parses_and_calls_engine(tmp_path, monkeypatch):
    captured = {}

    def fake_build(prompts, **kw):
        captured["prompts"] = prompts
        captured["kw"] = kw
        return {"path": "deck.pptx", "image_paths": ["s01.png", "s02.png"]}

    import cgimg.engine.decks as decks
    monkeypatch.setattr(decks, "build_slide_deck", fake_build)

    rc = cli.main([
        "deck", "--prompts", "Slide A", "Slide B",
        "--style", "slide", "--accent", "#10B981",
        "--reserve-corner", "top-left", "--thinking", "max",
        "--out", str(tmp_path / "d.pptx"),
    ])
    assert rc == 0
    assert captured["prompts"] == ["Slide A", "Slide B"]
    assert captured["kw"]["brand_colors"] == ["#10B981"]
    assert captured["kw"]["reserve_corner"] == "top-left"
    assert captured["kw"]["thinking"] == "max"
    assert captured["kw"]["style"] == "slide"


def test_deck_prompts_file_skips_blank_and_comments(tmp_path, monkeypatch):
    pf = tmp_path / "prompts.txt"
    pf.write_text("# comment\nFirst\n\nSecond\n", encoding="utf-8")
    captured = {}

    import cgimg.engine.decks as decks
    monkeypatch.setattr(
        decks, "build_slide_deck",
        lambda prompts, **kw: captured.update(prompts=prompts) or {"path": "d", "image_paths": []},
    )
    cli.main(["deck", "--prompts-file", str(pf), "--out", str(tmp_path / "d.pptx")])
    assert captured["prompts"] == ["First", "Second"]


def test_gen_accent_maps_to_brand_colors(monkeypatch):
    captured = {}
    import cgimg.engine.generate as gen
    monkeypatch.setattr(
        gen, "generate_image",
        lambda prompt, **kw: captured.update(kw) or ["x.png"],
    )
    cli.main(["gen", "hello", "--accent", "#123456", "--no-enhance"])
    assert captured["brand_colors"] == ["#123456"]
    assert captured["reserve_corner"] is None
    assert captured["enhance"] is False
