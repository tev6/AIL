"""Tests for `ail bundle` — turning scattered lifecycle files into one
evolve-server module. Telos 2026-04-29."""
from __future__ import annotations

from pathlib import Path

import pytest

from ail.bundle import (
    DEFAULT_LISTEN_PORT,
    DEFAULT_ROLLBACK_ON,
    bundle,
    detect_lifecycle_files,
    hook_name_from_path,
    _split_entry_main,
    _strip_header_comments,
)


def test_hook_name_from_path_recognizes_known_hooks(tmp_path):
    assert hook_name_from_path(Path("on_birth.ail")) == "on_birth"
    assert hook_name_from_path(Path("/x/y/on_genesis.ail")) == "on_genesis"
    assert hook_name_from_path(Path("before_tick.ail")) == "before_tick"
    # Unknown stem → None.
    assert hook_name_from_path(Path("app.ail")) is None
    assert hook_name_from_path(Path("random.ail")) is None
    # Wrong suffix → None.
    assert hook_name_from_path(Path("on_birth.txt")) is None


def test_split_entry_main_extracts_body_with_brace_matching():
    text = """\
intent foo() -> Text { goal: "x" }

entry main(input: Text) {
    if x {
        return "y"
    }
    return "z"
}
"""
    pre, body = _split_entry_main(text)
    assert "intent foo()" in pre
    assert body is not None
    assert "if x {" in body
    assert 'return "z"' in body
    # Outer closing brace was consumed; body has no trailing }.
    assert not body.endswith("}")


def test_split_entry_main_returns_none_when_no_entry():
    pre, body = _split_entry_main("pure fn helper() -> Text { return \"\" }")
    assert body is None
    assert pre


def test_strip_header_comments_drops_input_purpose_lines():
    text = """\
// INPUT: 비워두세요.
# PURPOSE: 첫 세대 초기화

intent foo() -> Text { goal: "x" }
"""
    cleaned = _strip_header_comments(text)
    assert "INPUT" not in cleaned
    assert "PURPOSE" not in cleaned
    assert "intent foo()" in cleaned


def test_bundle_combines_two_lifecycle_files(tmp_path):
    (tmp_path / "on_birth.ail").write_text(
        '// INPUT: 비워두세요.\n'
        '# PURPOSE: birth\n\n'
        'entry main(input: Text) {\n'
        '    return "born"\n'
        '}\n',
        encoding="utf-8",
    )
    (tmp_path / "on_tick.ail").write_text(
        'pure fn helper(x: Text) -> Text { return x }\n\n'
        'entry main(input: Text) {\n'
        '    return helper("tick")\n'
        '}\n',
        encoding="utf-8",
    )
    output = tmp_path / "agent.ail"
    result = bundle(
        [tmp_path / "on_birth.ail", tmp_path / "on_tick.ail"],
        output=output,
    )
    assert result.used_files == ["on_birth.ail", "on_tick.ail"]
    assert result.skipped_files == []
    assert output.is_file()
    src = output.read_text(encoding="utf-8")
    # Wrapped as fn-convention hooks.
    assert "fn on_birth() -> Text" in src
    assert "fn on_tick(state: Record) -> Text" in src
    # Top-level helper carried over.
    assert "pure fn helper(x: Text)" in src
    # Default Physis evolve block is present with required defaults.
    # Bundler emits `evolve heartbeat { ... }` — heartbeat is the
    # synthetic anchor intent; users replace with a real policy later.
    assert "evolve heartbeat {" in src
    assert "intent heartbeat()" in src
    assert "rollback_on: " + DEFAULT_ROLLBACK_ON in src
    assert f"listen: {DEFAULT_LISTEN_PORT}" in src
    assert "schedule: every(60)" in src
    # consecutive_failures is 1st-class in the default rollback_on
    # (Arche directive 2026-04-29).
    assert "consecutive_failures" in src


def test_bundle_skips_non_hook_files(tmp_path):
    (tmp_path / "on_birth.ail").write_text(
        'entry main(input: Text) { return "ok" }\n',
        encoding="utf-8",
    )
    (tmp_path / "random.ail").write_text(
        'entry main(input: Text) { return "x" }\n',
        encoding="utf-8",
    )
    output = tmp_path / "out.ail"
    result = bundle(
        [tmp_path / "on_birth.ail", tmp_path / "random.ail"],
        output=output,
    )
    assert result.used_files == ["on_birth.ail"]
    assert result.skipped_files == ["random.ail"]


def test_bundle_returns_empty_when_no_hooks_match(tmp_path):
    (tmp_path / "random.ail").write_text(
        'entry main(input: Text) { return "x" }\n',
        encoding="utf-8",
    )
    output = tmp_path / "out.ail"
    result = bundle([tmp_path / "random.ail"], output=output)
    assert result.used_files == []
    assert result.skipped_files == ["random.ail"]
    # No file written when nothing bundled.
    assert not output.exists()


def test_bundle_synthetic_entry_calls_on_birth_first(tmp_path):
    (tmp_path / "on_birth.ail").write_text(
        'entry main(input: Text) { return "ok" }\n',
        encoding="utf-8",
    )
    output = tmp_path / "out.ail"
    bundle([tmp_path / "on_birth.ail"], output=output)
    src = output.read_text(encoding="utf-8")
    assert "entry main(input: Text)" in src
    assert "return on_birth()" in src


def test_bundle_custom_listen_and_rollback(tmp_path):
    (tmp_path / "on_tick.ail").write_text(
        'entry main(input: Text) { return "tick" }\n',
        encoding="utf-8",
    )
    output = tmp_path / "out.ail"
    bundle(
        [tmp_path / "on_tick.ail"],
        output=output,
        listen=9999,
        rollback_on="error_rate > 0.9",
        schedule_seconds=10,
    )
    src = output.read_text(encoding="utf-8")
    assert "listen: 9999" in src
    assert "rollback_on: error_rate > 0.9" in src
    assert "schedule: every(10)" in src


def test_detect_lifecycle_files_finds_only_hook_stems(tmp_path):
    (tmp_path / "on_birth.ail").write_text(
        'entry main(input: Text) { return "" }\n', encoding="utf-8")
    (tmp_path / "on_tick.ail").write_text(
        'entry main(input: Text) { return "" }\n', encoding="utf-8")
    (tmp_path / "app.ail").write_text(
        'entry main(input: Text) { return "" }\n', encoding="utf-8")
    (tmp_path / "INTENT.md").write_text("# x\n", encoding="utf-8")
    found = detect_lifecycle_files(tmp_path)
    names = sorted(p.name for p in found)
    assert names == ["on_birth.ail", "on_tick.ail"]


def test_detect_lifecycle_files_skips_files_without_entry_main(tmp_path):
    (tmp_path / "on_birth.ail").write_text(
        '// just a comment, no entry main\n', encoding="utf-8")
    found = detect_lifecycle_files(tmp_path)
    assert found == []


def test_bundled_output_is_valid_ail(tmp_path):
    """The whole point: output must parse. If the bundler emits broken
    syntax, deploy is no closer than before."""
    (tmp_path / "on_birth.ail").write_text(
        'entry main(input: Text) {\n'
        '    return "born"\n'
        '}\n',
        encoding="utf-8",
    )
    (tmp_path / "on_tick.ail").write_text(
        'entry main(input: Text) {\n'
        '    return "tick"\n'
        '}\n',
        encoding="utf-8",
    )
    output = tmp_path / "out.ail"
    bundle(
        [tmp_path / "on_birth.ail", tmp_path / "on_tick.ail"],
        output=output,
    )
    src = output.read_text(encoding="utf-8")
    from ail import compile_source
    program = compile_source(src)
    # Program declares the lifecycle hooks + an evolve block + the
    # synthetic entry main.
    decl_kinds = {type(d).__name__ for d in program.declarations}
    assert "FnDecl" in decl_kinds
    assert "EvolveDecl" in decl_kinds
    assert "EntryDecl" in decl_kinds
