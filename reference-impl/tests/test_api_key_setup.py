"""Tests for the API key setup wizard (v1.66.3).

Covers:
- /save-key writes to ~/.ail/.env correctly
- /env-status returns has_llm_key=False when no key set
- /env-status returns has_llm_key=True after saving
- _load_dotenv_if_present picks up ~/.ail/.env as global fallback
- Unknown key_type returns 400
- Empty value returns 400
"""
import os
from pathlib import Path
from unittest.mock import patch


def _make_client(tmp_path):
    """Create a Flask test client with the home dir mocked to tmp_path."""
    from ail.agentic.home_ui import _make_app
    app = _make_app(tmp_path)
    app.testing = True
    return app.test_client(), tmp_path


def test_save_key_anthropic_writes_env_file(tmp_path):
    client, root = _make_client(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    with patch.dict(os.environ, {}, clear=False), \
         patch("pathlib.Path.home", return_value=home):
        # Remove ANTHROPIC_API_KEY so it's not already set
        os.environ.pop("ANTHROPIC_API_KEY", None)
        r = client.post("/save-key", json={"key_type": "anthropic", "value": "sk-ant-test123"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert data["var"] == "ANTHROPIC_API_KEY"
        env_file = home / ".ail" / ".env"
        assert env_file.is_file()
        content = env_file.read_text()
        assert "ANTHROPIC_API_KEY=sk-ant-test123" in content


def test_save_key_ollama_writes_correct_var(tmp_path):
    client, root = _make_client(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    with patch.dict(os.environ, {}, clear=False), \
         patch("pathlib.Path.home", return_value=home):
        os.environ.pop("AIL_OLLAMA_MODEL", None)
        r = client.post("/save-key", json={"key_type": "ollama", "value": "qwen2.5-coder:7b"})
        assert r.status_code == 200
        assert r.get_json()["var"] == "AIL_OLLAMA_MODEL"
        env_file = home / ".ail" / ".env"
        assert "AIL_OLLAMA_MODEL=qwen2.5-coder:7b" in env_file.read_text()


def test_save_key_unknown_type_returns_400(tmp_path):
    client, _ = _make_client(tmp_path)
    r = client.post("/save-key", json={"key_type": "google", "value": "xyz"})
    assert r.status_code == 400


def test_save_key_empty_value_returns_400(tmp_path):
    client, _ = _make_client(tmp_path)
    r = client.post("/save-key", json={"key_type": "anthropic", "value": ""})
    assert r.status_code == 400


def test_env_status_no_key_returns_has_llm_key_false(tmp_path):
    client, _ = _make_client(tmp_path)
    clean = {k: v for k, v in os.environ.items()
             if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY",
                          "AIL_OLLAMA_MODEL", "AIL_OPENAI_COMPAT_MODEL")}
    home = tmp_path / "home"
    home.mkdir()
    with patch.dict(os.environ, clean, clear=True), \
         patch("pathlib.Path.home", return_value=home):
        r = client.get("/env-status")
        assert r.status_code == 200
        j = r.get_json()
        assert j["has_llm_key"] is False


def test_env_status_after_save_returns_has_llm_key_true(tmp_path):
    client, _ = _make_client(tmp_path)
    clean = {k: v for k, v in os.environ.items()
             if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY",
                          "AIL_OLLAMA_MODEL", "AIL_OPENAI_COMPAT_MODEL")}
    home = tmp_path / "home"
    home.mkdir()
    with patch.dict(os.environ, clean, clear=True), \
         patch("pathlib.Path.home", return_value=home):
        # Before save
        assert client.get("/env-status").get_json()["has_llm_key"] is False
        # Save a key
        client.post("/save-key", json={"key_type": "anthropic", "value": "sk-ant-xyz"})
        # After save — env-status re-reads ~/.ail/.env
        assert client.get("/env-status").get_json()["has_llm_key"] is True


def test_global_dotenv_fallback(tmp_path):
    """_load_dotenv_if_present picks up ~/.ail/.env when no project .env."""
    from ail import _load_dotenv_file, _load_dotenv_if_present
    home = tmp_path / "home"
    (home / ".ail").mkdir(parents=True)
    global_env = home / ".ail" / ".env"
    global_env.write_text("AIL_OLLAMA_MODEL=test-model\n")
    clean = {k: v for k, v in os.environ.items()
             if k != "AIL_OLLAMA_MODEL"}
    with patch.dict(os.environ, clean, clear=True), \
         patch("pathlib.Path.home", return_value=home), \
         patch("pathlib.Path.cwd", return_value=tmp_path):
        _load_dotenv_if_present()
        assert os.environ.get("AIL_OLLAMA_MODEL") == "test-model"


def test_save_key_replaces_existing_entry(tmp_path):
    client, _ = _make_client(tmp_path)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".ail").mkdir()
    existing = home / ".ail" / ".env"
    existing.write_text("ANTHROPIC_API_KEY=old-key\nOTHER=kept\n")
    with patch.dict(os.environ, {}, clear=False), \
         patch("pathlib.Path.home", return_value=home):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        r = client.post("/save-key", json={"key_type": "anthropic", "value": "new-key"})
        assert r.status_code == 200
        content = existing.read_text()
        assert "ANTHROPIC_API_KEY=new-key" in content
        assert "old-key" not in content
        assert "OTHER=kept" in content
