import os

# config.py instantiates `config = ConfigStore(...)` at import time and refuses
# to load without an auth-key. Set a dummy one so the vendored modules import.
# (Import resolution only — real auth is wired at runtime, not import time.)
os.environ.setdefault("CHATGPT2API_AUTH_KEY", "cgimg-import-test")

import cgimg._vendor_path  # noqa: E402,F401  (side effect: sys.path)


def test_backend_api_imports():
    import importlib
    mod = importlib.import_module("services.openai_backend_api")
    assert hasattr(mod, "OpenAIBackendAPI")


def test_conversation_imports():
    import importlib
    mod = importlib.import_module("services.protocol.conversation")
    assert hasattr(mod, "stream_image_outputs")


def test_image_storage_imports():
    import importlib
    mod = importlib.import_module("services.image_storage_service")
    assert hasattr(mod, "image_storage_service")


def test_vendored_imports_without_preset_auth_key():
    """Regression: the login / accounts paths import vendored code via
    _vendor_path WITHOUT separately setting CHATGPT2API_AUTH_KEY. _vendor_path
    must set it so the vendored config can import - otherwise the get_user_info
    probe fails silently and accounts show no email/quota. Run in a fresh process
    with the key removed to prove _vendor_path alone is sufficient."""
    import subprocess
    import sys

    clean_env = {k: v for k, v in os.environ.items() if k != "CHATGPT2API_AUTH_KEY"}
    code = "import cgimg._vendor_path; import services.openai_backend_api; print('ok')"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, env=clean_env)
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
