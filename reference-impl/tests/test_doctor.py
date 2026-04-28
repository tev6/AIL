"""Tests for `ail doctor` — the project sanity checker.

Telos 2026-04-29. The 5-second version of what would otherwise be a
30-min Arche-project debugging session.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ail.doctor import (
    Finding,
    diagnose,
    render_report,
)


def _write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_doctor_clean_project_returns_empty_findings(tmp_path):
    proj = tmp_path / "clean"
    proj.mkdir()
    _write(proj / "main.ail",
           "entry main(input: Text) { return ok(input) }\n")
    _write(proj / "INTENT.md", "# clean\n\nA real project.\n")
    report = diagnose(proj)
    assert report.findings == []


def test_doctor_flags_scattered_lifecycle_without_evolve(tmp_path):
    """The Arche project pattern — main fault."""
    proj = tmp_path / "arche-like"
    proj.mkdir()
    _write(proj / "on_birth.ail",
           "entry main(input: Text) { return ok(input) }\n")
    _write(proj / "on_tick.ail",
           "entry main(input: Text) { return ok(input) }\n")
    _write(proj / "INTENT.md", "# x\n\ndoes things\n")
    report = diagnose(proj)
    codes = {f.code for f in report.findings}
    assert "scattered_lifecycle_no_evolve" in codes
    finding = next(
        f for f in report.findings
        if f.code == "scattered_lifecycle_no_evolve"
    )
    # Hint includes the concrete `ail bundle` command for the user.
    assert "ail bundle on_birth.ail on_tick.ail" in finding.hint


def test_doctor_flags_scaffold_app_ail(tmp_path):
    proj = tmp_path / "scaff"
    proj.mkdir()
    _write(proj / "app.ail", (
        'pure fn process_input(s: Text) -> Result {\n'
        '    if length(trim(s)) == 0 {\n'
        '        return error("Input cannot be empty")\n'
        '    }\n'
        '    return ok(s)\n'
        '}\n'
        'entry main(input: Text) { return process_input(input) }\n'
    ))
    _write(proj / "INTENT.md", "# x\n\nreal\n")
    report = diagnose(proj)
    codes = {f.code for f in report.findings}
    assert "scaffold_app_ail" in codes


def test_doctor_flags_paused_schedule(tmp_path):
    proj = tmp_path / "paused"
    proj.mkdir()
    _write(proj / "main.ail",
           "entry main(input: Text) {\n"
           "    perform schedule.every(10)\n"
           "    return ok(input)\n"
           "}\n")
    _write(proj / "INTENT.md", "# x\n\nrecurring\n")
    _write(proj / ".ail" / "schedule.json", json.dumps({
        "seconds": 10,
        "paused": True,
        "paused_reason": "Input cannot be empty",
        "paused_consecutive_failures": 5,
    }))
    report = diagnose(proj)
    codes = {f.code for f in report.findings}
    assert "schedule_paused" in codes
    finding = next(f for f in report.findings if f.code == "schedule_paused")
    assert "5번 연속 실패" in finding.message
    assert "다시 켜기" in finding.hint


def test_doctor_flags_orphan_schedule_json(tmp_path):
    """schedule.json present but no .ail registers it."""
    proj = tmp_path / "orphan"
    proj.mkdir()
    _write(proj / "main.ail",
           "entry main(input: Text) { return ok(input) }\n")
    _write(proj / "INTENT.md", "# x\n\nx\n")
    _write(proj / ".ail" / "schedule.json", json.dumps({"seconds": 10}))
    report = diagnose(proj)
    codes = {f.code for f in report.findings}
    assert "orphan_schedule_json" in codes


def test_doctor_flags_active_program_marker_pointing_at_missing_file(tmp_path):
    proj = tmp_path / "stale"
    proj.mkdir()
    _write(proj / "real.ail",
           "entry main(input: Text) { return ok(input) }\n")
    _write(proj / "INTENT.md", "# x\n\nx\n")
    _write(proj / ".ail" / "active_program", "deleted.ail")
    report = diagnose(proj)
    codes = {f.code for f in report.findings}
    assert "active_program_missing" in codes


def test_doctor_flags_parse_error(tmp_path):
    proj = tmp_path / "broken"
    proj.mkdir()
    _write(proj / "broken.ail",
           "entry main(input: Text) {\n  return (((\n}\n")
    _write(proj / "INTENT.md", "# x\n\nx\n")
    report = diagnose(proj)
    codes = {f.code for f in report.findings}
    assert "parse_error" in codes
    # Severity is error — `ail doctor` exit code should be non-zero.
    assert any(f.severity == "error" for f in report.findings)


def test_doctor_flags_no_entry_main(tmp_path):
    proj = tmp_path / "no_entry"
    proj.mkdir()
    _write(proj / "helper.ail",
           "pure fn h(x: Text) -> Text { return x }\n")
    _write(proj / "INTENT.md", "# x\n\nx\n")
    report = diagnose(proj)
    codes = {f.code for f in report.findings}
    assert "no_entry_main" in codes


def test_doctor_renders_clean_report(tmp_path):
    proj = tmp_path / "ok"
    proj.mkdir()
    _write(proj / "main.ail",
           "entry main(input: Text) { return ok(input) }\n")
    _write(proj / "INTENT.md", "# ok\n\nreal\n")
    text = render_report(diagnose(proj))
    assert "✅ 모든 검사 통과" in text


def test_doctor_renders_report_with_findings(tmp_path):
    proj = tmp_path / "broken"
    proj.mkdir()
    _write(proj / "broken.ail",
           "entry main(input: Text) {\n  return (((\n}\n")
    _write(proj / "INTENT.md", "# x\n\nx\n")
    text = render_report(diagnose(proj))
    assert "❌" in text
    assert "parse_error" in text
    # Hint line is rendered with → marker.
    assert "→" in text


def test_doctor_findings_sort_errors_before_warnings(tmp_path):
    """Errors should be listed first so the user reads them top-down."""
    proj = tmp_path / "mixed"
    proj.mkdir()
    _write(proj / "broken.ail",
           "entry main(input: Text) {\n  return (((\n}\n")
    _write(proj / "INTENT.md",
           "# x\n\nA short paragraph describing what this service should do\n")
    report = diagnose(proj)
    assert report.findings[0].severity == "error"
    severities = [f.severity for f in report.findings]
    # errors → warnings → infos invariant
    error_idx = [i for i, s in enumerate(severities) if s == "error"]
    info_idx = [i for i, s in enumerate(severities) if s == "info"]
    if error_idx and info_idx:
        assert max(error_idx) < min(info_idx)
