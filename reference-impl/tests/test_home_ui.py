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
    j = r.get_json()
    # The structured 409 the UI uses to enter the trash-and-retry flow.
    assert j.get("error_code") == "name_exists"
    assert "existing_path" in j


def test_trash_polis_moves_to_trashcan(client, monkeypatch, tmp_path):
    """Existing polis dir → moved to ~/.ail/.Trashcan/<ts>-<name>/.
    Confirms HEAAL: no destructive deletion at the AIL layer; the UI
    offers move-to-trash with explicit confirm."""
    c, root = client
    # Stub HOME so the trashcan lands somewhere we can inspect.
    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    monkeypatch.setattr("pathlib.Path.home", lambda: fake_home)
    target = root / "alpha"  # has INTENT.md (fixture)
    assert target.exists()
    r = c.post("/trash-polis",
               json={"path": str(target), "confirm": True})
    assert r.status_code == 200, r.get_json()
    j = r.get_json()
    assert j["ok"] is True
    moved_to = j["moved_to"]
    assert "Trashcan" in moved_to
    # Source gone, trash entry exists
    assert not target.exists()
    from pathlib import Path as _P
    assert (_P(moved_to) / "INTENT.md").exists()


def test_trash_polis_requires_confirm(client):
    c, root = client
    r = c.post("/trash-polis", json={"path": str(root / "alpha")})
    assert r.status_code == 400
    assert r.get_json().get("error_code") == "confirm_required"


def test_trash_polis_refuses_non_polis_non_empty(client, tmp_path):
    """Defensive: refuse to trash a directory that is not a polis
    AND not empty. Stops the UI from accidentally trashing /Users
    or a project root that happens to share a name."""
    c, root = client
    # `beta` exists from fixture but has no INTENT.md and isn't empty
    # (well — actually it IS empty in the fixture). Make it non-empty
    # to trigger the guard.
    (root / "beta" / "random.txt").write_text("not a polis")
    r = c.post("/trash-polis",
               json={"path": str(root / "beta"), "confirm": True})
    assert r.status_code == 400
    assert r.get_json().get("error_code") == "not_a_polis"


def test_trash_polis_404_for_missing_path(client):
    c, root = client
    r = c.post("/trash-polis",
               json={"path": str(root / "no_such_dir"), "confirm": True})
    assert r.status_code == 404


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
