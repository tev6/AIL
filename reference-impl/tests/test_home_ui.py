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


def test_check_port_endpoint(client):
    """`/check-port?port=N` returns {alive: bool} so the frontend can
    wait for `ail up` to actually accept connections before opening
    the browser tab. Used after the 30s blind-timeout regression."""
    c, _ = client
    # Port 1 is reserved (TCPMUX) — almost certainly closed
    r = c.get("/check-port?port=1")
    assert r.status_code == 200
    j = r.get_json()
    assert j["alive"] is False
    assert j["port"] == 1


def test_check_port_rejects_bad_input(client):
    c, _ = client
    r = c.get("/check-port?port=abc")
    assert r.status_code == 400
    r = c.get("/check-port?port=99999")
    assert r.status_code == 400


def test_spawn_log_endpoint_rejects_paths_outside_log_root(client, tmp_path):
    """Defensive: /spawn-log must only serve files under
    ~/.ail/logs/. Asking for /etc/passwd or anywhere else is denied."""
    c, _ = client
    r = c.get("/spawn-log?path=/etc/passwd")
    assert r.status_code == 400


def test_trash_confirm_dialog_uses_real_newlines(client):
    """The confirm() string in window.confirm must use a single JS
    escape `\\n` (2 chars in the HTML) so the dialog shows newlines.
    Pre-fix the Python source had double-escaped `\\\\n` (4 chars
    `\\\\n` in Python = 2 chars `\\n` in HTML output → JS sees the
    `\\n` escape *for backslash* + literal `n` → user saw '\\n' as
    text, not newline). Post-fix the Python source has `\\n` which
    in the raw triple-string stays as 2 chars `\\n` in HTML output →
    JS treats as newline escape. Field-test fix (hyun06000 2026-04-27).
    """
    c, _ = client
    r = c.get("/")
    body = r.get_data(as_text=True)
    snippet_start = body.find("휴지통(~/.ail/.Trashcan/)")
    assert snippet_start != -1, "trash dialog text missing"
    region = body[snippet_start - 100:snippet_start + 250]
    # The HTML must NOT contain the 3-char `\\n` (Python "\\\\n") —
    # that's the broken double-escape JS would render as literal `\n`.
    assert "\\\\n" not in region, (
        "Trash confirm dialog double-escapes newline — JS will show "
        r"literal '\n' text instead of breaking lines. Use single "
        "backslash + n in the raw-string source, not double.")
    # Sanity: the proper 2-char `\n` JS escape IS present (some \n's
    # exist in the dialog source).
    assert "\\n" in region


def test_open_polis_rejects_non_polis(client):
    c, root = client
    r = c.post("/open-polis", json={"path": str(root / "beta")})
    assert r.status_code == 400


def test_admin_stop_endpoint_returns_ok(client, monkeypatch):
    """Closing the browser tab triggers sendBeacon('/admin/stop') so
    the terminal `ail` process exits too (non-developer UX). The
    endpoint schedules SIGTERM in a daemon thread — we stub
    threading.Thread so the suicide thread never runs (otherwise it
    fires after monkeypatch teardown and kills the test runner;
    CI exit 143 in v1.64.4)."""
    import threading
    class _NoopThread:
        def __init__(self, *a, **kw): pass
        def start(self): pass
    monkeypatch.setattr(threading, "Thread", _NoopThread)
    c, _ = client
    r = c.post("/admin/stop")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_env_status_returns_known_vars(client):
    c, _ = client
    r = c.get("/env-status")
    j = r.get_json()
    names = [v["var"] for v in j["vars"]]
    for required in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "AIL_OLLAMA_MODEL"]:
        assert required in names
