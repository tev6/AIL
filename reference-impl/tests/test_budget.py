"""Tests for the `budget.*` effect surface — AIL#23 G5 (cycle 13).

Six regression cases from RFC §8:
- charge within ceiling (sum + monotone remaining)
- charge exceeds ceiling (atomic: state NOT updated, error returned)
- unconfigured category errors (no silent uncapped run)
- reset zeroes consumed (ceiling unchanged)
- negative amount rejected (validation)
- ledger event shape (G7 cross-link)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str, *, state_dir: Path, identity: str,
         config_dir: Path | None = None, monkeypatch=None):
    program = compile_source(src)
    monkeypatch.setenv("AIL_STATE_DIR", str(state_dir))
    monkeypatch.setenv("STOA_NAME", identity)
    if config_dir is not None:
        monkeypatch.setenv("AIL_BUDGET_CONFIG", str(config_dir))
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": ""})


@pytest.fixture()
def telos_budget(tmp_path, monkeypatch):
    """A telos identity with llm_tokens ceiling=100 configured."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    cfg_dir = tmp_path / "budget"
    cfg_dir.mkdir()
    (cfg_dir / "telos.yaml").write_text(
        "llm_tokens:\n  ceiling: 100\n  period: daily\n",
        encoding="utf-8",
    )
    return state_dir, cfg_dir, monkeypatch


def test_charge_within_ceiling_returns_remaining(telos_budget):
    state_dir, cfg_dir, mp = telos_budget
    cv = _run(
        'entry main(input: Text) {\n'
        '  a_r = perform budget.charge("llm_tokens", 30)\n'
        '  a = unwrap(a_r)\n'
        '  b_r = perform budget.charge("llm_tokens", 20)\n'
        '  b = unwrap(b_r)\n'
        '  r_r = perform budget.remaining("llm_tokens")\n'
        '  r = unwrap(r_r)\n'
        '  return join([to_text(a), "|", to_text(b), "|", to_text(r)], "")\n'
        '}\n',
        state_dir=state_dir, identity="telos", config_dir=cfg_dir,
        monkeypatch=mp,
    )
    assert cv.value == "70|50|50"


def test_charge_exceeds_ceiling_is_atomic(telos_budget):
    """Over-budget charge must NOT update consumed; the next remaining
    must equal the value before the over-budget attempt."""
    state_dir, cfg_dir, mp = telos_budget
    cv = _run(
        'entry main(input: Text) {\n'
        '  a_r = perform budget.charge("llm_tokens", 80)\n'
        '  a = unwrap(a_r)\n'
        '  bad_r = perform budget.charge("llm_tokens", 50)\n'
        '  bad_msg = ""\n'
        '  if is_error(bad_r) { bad_msg = unwrap_error(bad_r) }\n'
        '  r_r = perform budget.remaining("llm_tokens")\n'
        '  r = unwrap(r_r)\n'
        '  return join([to_text(a), "|", bad_msg, "|", to_text(r)], "")\n'
        '}\n',
        state_dir=state_dir, identity="telos", config_dir=cfg_dir,
        monkeypatch=mp,
    )
    parts = cv.value.split("|")
    a, bad_msg, r = parts
    assert a == "20"                              # 100 - 80
    assert bad_msg.startswith("budget_exceeded:")
    assert "llm_tokens" in bad_msg
    assert r == "20"                              # unchanged after rejected charge


def test_unconfigured_category_errors(telos_budget):
    """Charging an unknown category surfaces the gap instead of
    silently allowing uncapped spend."""
    state_dir, cfg_dir, mp = telos_budget
    cv = _run(
        'entry main(input: Text) {\n'
        '  r = perform budget.charge("compute_minutes", 1)\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "should not get here"\n'
        '}\n',
        state_dir=state_dir, identity="telos", config_dir=cfg_dir,
        monkeypatch=mp,
    )
    assert cv.value.startswith("budget_unconfigured:")
    assert "compute_minutes" in cv.value


def test_reset_zeros_consumed_ceiling_unchanged(telos_budget):
    state_dir, cfg_dir, mp = telos_budget
    cv = _run(
        'entry main(input: Text) {\n'
        '  perform budget.charge("llm_tokens", 60)\n'
        '  before_r = perform budget.remaining("llm_tokens")\n'
        '  before = unwrap(before_r)\n'
        '  reset_r = perform budget.reset("llm_tokens")\n'
        '  reset_v = unwrap(reset_r)\n'
        '  after_r = perform budget.remaining("llm_tokens")\n'
        '  after = unwrap(after_r)\n'
        '  return join([to_text(before), "|", to_text(reset_v), "|", to_text(after)], "")\n'
        '}\n',
        state_dir=state_dir, identity="telos", config_dir=cfg_dir,
        monkeypatch=mp,
    )
    assert cv.value == "40|100|100"


def test_negative_amount_rejected(telos_budget):
    state_dir, cfg_dir, mp = telos_budget
    cv = _run(
        'entry main(input: Text) {\n'
        '  r = perform budget.charge("llm_tokens", -5)\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "should not get here"\n'
        '}\n',
        state_dir=state_dir, identity="telos", config_dir=cfg_dir,
        monkeypatch=mp,
    )
    assert "amount must be > 0" in cv.value


def test_anonymous_identity_uses_fixed_defaults(tmp_path, monkeypatch):
    """No config dir + STOA_NAME unset + not inside agents/<name>/ →
    identity = anonymous, ceilings = fixed safe defaults
    (llm_tokens=100, compute_minutes=1, stoa_push=5)."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    monkeypatch.setenv("AIL_STATE_DIR", str(state_dir))
    monkeypatch.delenv("STOA_NAME", raising=False)
    monkeypatch.delenv("AIL_BUDGET_CONFIG", raising=False)
    monkeypatch.delenv("AIL_IDENTITY", raising=False)

    program = compile_source(
        'entry main(input: Text) {\n'
        '  r1 = perform budget.remaining("llm_tokens")\n'
        '  r2 = perform budget.remaining("compute_minutes")\n'
        '  r3 = perform budget.remaining("stoa_push")\n'
        '  return join([to_text(unwrap(r1)), "|", to_text(unwrap(r2)), "|", to_text(unwrap(r3))], "")\n'
        '}\n'
    )
    ex = Executor(program, MockAdapter())
    cv = ex.run_entry({"input": ""})
    assert cv.value == "100|1|5"


def test_ledger_event_shape(telos_budget):
    """Every charge and reset must emit a `budget` trace row with the
    G7-ready schema (event/identity/category/consumed_after/ceiling/ts).
    """
    state_dir, cfg_dir, mp = telos_budget
    program = compile_source(
        'entry main(input: Text) {\n'
        '  perform budget.charge("llm_tokens", 25)\n'
        '  perform budget.reset("llm_tokens")\n'
        '  return "ok"\n'
        '}\n'
    )
    mp.setenv("AIL_STATE_DIR", str(state_dir))
    mp.setenv("AIL_BUDGET_CONFIG", str(cfg_dir))
    mp.setenv("STOA_NAME", "telos")
    ex = Executor(program, MockAdapter())
    ex.run_entry({"input": ""})

    rows = [e.payload for e in ex.trace.entries if e.kind == "budget"]
    assert len(rows) == 2
    charge_row, reset_row = rows
    for row in rows:
        for key in ("event", "identity", "category",
                    "consumed_after", "ceiling", "ts"):
            assert key in row, f"missing {key} in {row}"
        assert row["identity"] == "telos"
        assert row["category"] == "llm_tokens"
        assert row["ceiling"] == 100
    assert charge_row["event"] == "budget_charge"
    assert charge_row["amount"] == 25
    assert charge_row["consumed_after"] == 25
    assert reset_row["event"] == "budget_reset"
    assert "amount" not in reset_row
    assert reset_row["consumed_after"] == 0
