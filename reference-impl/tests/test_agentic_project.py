"""Project class tests — init, ledger writes, app.ail round-trip."""
import json
from pathlib import Path

import pytest

from ail.agentic.project import Project


def test_init_creates_layout(tmp_path):
    proj = Project.init(tmp_path / "demo")
    # Telos + Arche 2026-04-29 rebuild — Project.init no longer writes
    # INTENT.md. The .ail/ state dir is the only required scaffolding.
    assert not proj.intent_path.exists()
    assert proj.state_dir.exists()
    assert proj.ledger_path.exists()
    # Ledger entry records the project name (now passed via record,
    # not via a heading inside INTENT.md).
    lines = proj.ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"] == "init"
    assert rec["name"] == "demo"


def test_init_explicit_name_recorded_in_ledger(tmp_path):
    proj = Project.init(tmp_path / "folder", name="My App")
    rec = json.loads(
        proj.ledger_path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["name"] == "My App"


def test_init_idempotent(tmp_path):
    """Re-running Project.init on an existing project is a no-op now
    that there's no INTENT.md to clobber."""
    Project.init(tmp_path / "demo")
    # Should not raise.
    Project.init(tmp_path / "demo")
    # Both calls left an init ledger entry — that's fine; the ledger is
    # append-only and records the *intent* of each call.
    lines = (tmp_path / "demo" / ".ail" / "ledger.jsonl").read_text(
        encoding="utf-8").splitlines()
    assert len(lines) == 2


def test_at_auto_inits_empty_directory(tmp_path):
    """Arche directive 2026-04-29: no bare-terminal user should hit a
    dead end. `Project.at` on an empty directory now auto-creates
    `.ail/` instead of raising FileNotFoundError."""
    target = tmp_path / "empty"
    target.mkdir()
    proj = Project.at(target)
    assert proj.state_dir.is_dir()
    # Ledger has one init record from the auto-init.
    rec = json.loads(
        proj.ledger_path.read_text(encoding="utf-8").splitlines()[0])
    assert rec["event"] == "init"


def test_at_raises_when_directory_does_not_exist(tmp_path):
    with pytest.raises(FileNotFoundError):
        Project.at(tmp_path / "does-not-exist")


def test_at_opens_existing(tmp_path):
    Project.init(tmp_path / "demo")
    proj = Project.at(tmp_path / "demo")
    spec = proj.read_intent()
    # Empty IntentSpec because no INTENT.md exists — name falls back
    # to the directory name.
    assert spec.name == "demo"
    assert spec.behavior == []
    assert spec.tests == []


def test_app_source_round_trip(tmp_path):
    proj = Project.init(tmp_path / "demo")
    assert proj.read_app_source() == ""
    proj.write_app_source("entry main(x: Text) { return x }")
    txt = proj.read_app_source()
    assert "entry main" in txt
    assert txt.endswith("\n")  # normalized


def test_ledger_appends(tmp_path):
    proj = Project.init(tmp_path / "demo")
    proj.append_ledger({"event": "test", "n": 1})
    proj.append_ledger({"event": "test", "n": 2})
    lines = proj.ledger_path.read_text(encoding="utf-8").splitlines()
    # init + 2 manual = 3 records
    assert len(lines) == 3
    last = json.loads(lines[-1])
    assert last["event"] == "test" and last["n"] == 2
    assert "ts" in last


def test_save_failed_attempt_creates_file_with_header(tmp_path):
    proj = Project.init(tmp_path / "demo")
    src = "pure fn x() {\n    bad: List = []\n}\n"
    errors = [
        "ParseError: unexpected token COLON(':')@2:9",
        "ParseError: previous attempt also COLON",
    ]
    path = proj.save_failed_attempt(
        source=src, errors=errors,
        author_model="anthropic/claude-sonnet-4-5",
        kind="author",
    )
    assert path.exists()
    assert path.parent == proj.attempts_dir
    body = path.read_text(encoding="utf-8")
    # Header records metadata
    assert "author_model:" in body
    assert "claude-sonnet-4-5" in body
    assert "[1] ParseError" in body
    assert "[2] ParseError" in body
    # Source is preserved verbatim after the header
    assert "pure fn x()" in body
    assert "bad: List = []" in body


def test_save_failed_attempt_creates_attempts_dir_if_missing(tmp_path):
    proj = Project.init(tmp_path / "demo")
    # Project.init shouldn't pre-create attempts_dir; it appears on demand.
    assert not proj.attempts_dir.exists()
    proj.save_failed_attempt(
        source="entry main(x: Text) {}", errors=["err"],
        author_model="x", kind="author",
    )
    assert proj.attempts_dir.is_dir()


def test_write_tests_extracts_from_intent(tmp_path):
    proj = Project.init(tmp_path / "demo")
    spec = proj.read_intent()
    proj.write_tests(spec)
    payload = json.loads(proj.tests_path.read_text(encoding="utf-8"))
    # Telos 2026-04-29: scaffold no longer plants placeholder tests
    # (they used to teach the author model to write `if is_empty(input)
    # { return error(...) }` literally — see Arche field test). A
    # fresh project's tests file should be an empty list.
    assert payload == []
