from cgimg.engine import enhance


def test_long_prompt_skipped():
    long = "x " * 200  # > 280 chars
    assert enhance.enhance_prompt(long).strip() == long.strip()


def test_template_fallback_is_rich(monkeypatch):
    # Force the LLM path to fail -> must fall back to template, never raise.
    import cgimg.auth.tokens as t
    monkeypatch.setattr(t, "get_access_token", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = enhance.enhance_prompt("ai agent")
    assert "ai agent" in out.lower()
    assert len(out) > len("ai agent")  # got enriched


def test_fintech_style_template_fallback(monkeypatch):
    # style="fintech" must be accepted; force the LLM path to fail so the
    # fintech template fallback runs -> non-empty string containing the input.
    import cgimg.auth.tokens as t
    monkeypatch.setattr(t, "get_access_token", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = enhance.enhance_prompt("fraud detection", style="fintech")
    assert "fraud detection" in out.lower()
    assert len(out) > len("fraud detection")  # got enriched


def test_template_enhance_offline_with_brand():
    # Public deterministic path (NO network): slide template + brand clause.
    out = enhance.template_enhance("Trí tuệ nhân tạo", style="slide",
                                   brand_colors=["#10B981"], reserve_corner="top-left")
    assert "Trí tuệ nhân tạo" in out          # input preserved WITH diacritics
    assert "#10B981" in out                    # brand color injected
    assert "top-left" in out                   # reserved corner injected
    assert len(out) > len("Trí tuệ nhân tạo")  # enriched by the template


def test_template_enhance_auto_no_brand():
    out = enhance.template_enhance("data pipeline")
    assert "data pipeline" in out
    assert "brand color palette" not in out  # no brand clause when none given
