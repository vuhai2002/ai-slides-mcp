"""Offline tests for the per-request thinking_effort hook (no network)."""
import inspect

import pytest

from cgimg.engine import image_thinking
from services.openai_backend_api import OpenAIBackendAPI


@pytest.fixture
def api():
    image_thinking.set_thinking("auto")
    yield OpenAIBackendAPI.__new__(OpenAIBackendAPI)  # no session/network needed
    image_thinking.set_thinking("auto")


def test_auto_keeps_upstream_default(api):
    model, effort = api._image_model_settings("gpt-image-2")
    assert model == "gpt-5-5"
    assert effort == ""  # upstream default_thinking_effort="auto" -> no field


@pytest.mark.parametrize("level", ["standard", "extended", "max"])
def test_level_overrides_effort(api, level):
    image_thinking.set_thinking(level)
    assert api._image_model_settings("gpt-image-2") == ("gpt-5-5", level)


def test_invalid_level_rejected():
    with pytest.raises(ValueError):
        image_thinking.set_thinking("high")


def test_patch_installed_once():
    assert getattr(OpenAIBackendAPI._image_model_settings, "_cgimg_thinking", False)


@pytest.mark.parametrize("method", ["_prepare_image_conversation", "_start_image_generation"])
def test_both_image_requests_read_the_hook(method):
    # If a vendor update stops routing effort through _image_model_settings, the
    # per-request thinking level would silently stop reaching the backend.
    src = inspect.getsource(getattr(OpenAIBackendAPI, method))
    assert "self._image_model_settings(model)" in src
    assert 'payload["thinking_effort"] = thinking_effort' in src
