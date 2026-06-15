"""Phase 05: partial deck on quota exhaustion (decks + branding)."""
import cgimg.engine.decks as decks
import pytest


def _fake_png(path):
    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n")


def test_partial_on_exhaustion(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    n = {"i": 0}

    def fake_gen(prompt, **kw):
        n["i"] += 1
        if n["i"] == 3:
            raise RuntimeError("boom")
        p = out / f"raw{n['i']}.png"
        _fake_png(p)
        return [str(p)]

    monkeypatch.setattr(decks, "generate_image", fake_gen)
    monkeypatch.setattr(decks, "build_pptx", lambda imgs, outp, aspect: str(outp))
    monkeypatch.setattr(decks, "pool_exhausted_reset",
                        lambda: (True, "2026-06-15T14:30:00+00:00"))
    res = decks.build_slide_deck(["A", "B", "C", "D"], out_dir=str(out),
                                 out_pptx=str(tmp_path / "d.pptx"), enhance=False)
    assert res["incomplete"] is True
    assert res["generated"] == 2 and res["total"] == 4
    assert res["reset_at"] == "2026-06-15T14:30:00+00:00"
    assert len(res["image_paths"]) == 2 and res["path"]


def test_exhaust_at_slide_one_writes_no_pptx(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    built = {"n": 0}
    monkeypatch.setattr(decks, "generate_image",
                        lambda prompt, **kw: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(decks, "build_pptx",
                        lambda *a, **k: built.update(n=built["n"] + 1) or "x")
    monkeypatch.setattr(decks, "pool_exhausted_reset", lambda: (True, "RESET"))
    res = decks.build_slide_deck(["A", "B"], out_dir=str(out),
                                 out_pptx=str(tmp_path / "d.pptx"), enhance=False)
    assert res["generated"] == 0 and res["path"] is None and res["incomplete"] is True
    assert built["n"] == 0  # no empty deck written


def test_non_quota_error_reraises(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(decks, "generate_image",
                        lambda prompt, **kw: (_ for _ in ()).throw(RuntimeError("content policy")))
    monkeypatch.setattr(decks, "pool_exhausted_reset", lambda: (False, None))
    with pytest.raises(RuntimeError, match="content policy"):
        decks.build_slide_deck(["A"], out_dir=str(out),
                               out_pptx=str(tmp_path / "d.pptx"), enhance=False)


def test_full_success_is_not_incomplete(tmp_path, monkeypatch):
    out = tmp_path / "out"
    out.mkdir()
    k = {"i": 0}

    def gen(prompt, **kw):
        k["i"] += 1
        p = out / f"raw{k['i']}.png"
        _fake_png(p)
        return [str(p)]

    monkeypatch.setattr(decks, "generate_image", gen)
    monkeypatch.setattr(decks, "build_pptx", lambda imgs, outp, aspect: str(outp))
    res = decks.build_slide_deck(["A", "B"], out_dir=str(out),
                                 out_pptx=str(tmp_path / "d.pptx"), enhance=False)
    assert res["incomplete"] is False
    assert res["generated"] == 2 == res["total"]
    assert res["reset_at"] is None


def test_branded_partial_keeps_brand_colors(tmp_path, monkeypatch):
    import cgimg.branding.deck as bd
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(bd, "extract_brand_colors", lambda p: ["#123456"])
    monkeypatch.setattr(bd, "enhance_prompt", lambda prompt, **kw: prompt)
    monkeypatch.setattr(bd, "overlay_logo", lambda src, logo, dst, **k: _fake_png(dst))
    monkeypatch.setattr(bd, "pool_exhausted_reset", lambda: (True, "RESET"))
    monkeypatch.setattr(decks, "build_pptx", lambda imgs, outp, aspect: str(outp))
    n = {"i": 0}

    def fake_gen(prompt, **kw):
        n["i"] += 1
        if n["i"] == 2:
            raise RuntimeError("boom")
        p = out / f"raw{n['i']}.png"
        _fake_png(p)
        return [str(p)]

    monkeypatch.setattr(bd, "generate_image", fake_gen)
    res = bd.branded_deck("logo.png", ["A", "B", "C"], out_dir=str(out),
                          out_pptx=str(tmp_path / "d.pptx"))
    assert res["incomplete"] is True
    assert res["generated"] == 1 and res["total"] == 3
    assert res["brand_colors"] == ["#123456"]
    assert res["reset_at"] == "RESET"
