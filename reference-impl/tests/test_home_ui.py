"""home_ui smoke tests — bare `ail` browser landing."""
import os
import tempfile
from pathlib import Path

import pytest

from ail.agentic.home_ui import _make_app


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "alpha").mkdir()
        (root / "beta").mkdir()
        (root / "alpha" / "INTENT.md").write_text("# alpha polis\n")
        (root / "readme.txt").write_text("hi\n")
        app = _make_app(root)
        app.testing = True
        yield app.test_client(), root


def test_index_renders(client):
    c, _ = client
    r = c.get("/")
    assert r.status_code == 200
    assert b"AIL" in r.data and b"create-btn" in r.data


def test_tree_lists_entries_and_marks_polis(client):
    c, root = client
    r = c.get(f"/tree?path={root}")
    assert r.status_code == 200
    j = r.get_json()
    names = {e["name"]: e for e in j["entries"]}
    assert "alpha" in names and names["alpha"]["is_polis"] is True
    assert "beta" in names and names["beta"]["is_polis"] is False
    assert names["readme.txt"]["is_dir"] is False


def test_tree_rejects_file_path(client):
    c, root = client
    r = c.get(f"/tree?path={root}/readme.txt")
    assert r.status_code == 400


def test_create_polis_validates_name(client):
    c, root = client
    r = c.post("/create-polis", json={"parent": str(root), "name": "../escape"})
    assert r.status_code == 400


def test_create_polis_rejects_existing(client):
    c, root = client
    r = c.post("/create-polis", json={"parent": str(root), "name": "alpha"})
    assert r.status_code == 409


def test_open_polis_rejects_non_polis(client):
    c, root = client
    r = c.post("/open-polis", json={"path": str(root / "beta")})
    assert r.status_code == 400


def test_env_status_returns_known_vars(client):
    c, _ = client
    r = c.get("/env-status")
    j = r.get_json()
    names = [v["var"] for v in j["vars"]]
    for required in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AIL_OLLAMA_MODEL"]:
        assert required in names
