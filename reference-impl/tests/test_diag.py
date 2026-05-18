"""Tests for `diag.*` runtime-introspection effects (cycle 13).

Six cases mirror RFC §6 (`docs/proposals/diag-effects.md`):
- gc_count returns three generations
- object_count is nonzero
- thread_count ≥ 1
- tracemalloc start → snapshot returns well-formed rows
- snapshot without prior start surfaces tracemalloc_not_started
- stop is idempotent (no error when not running)
"""
from __future__ import annotations

import tracemalloc

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


@pytest.fixture(autouse=True)
def _ensure_tracemalloc_stopped_around_each_test():
    # Tracemalloc state is process-global. Snap it to "stopped"
    # both before and after every test so cases that depend on
    # the start-or-not state are deterministic.
    if tracemalloc.is_tracing():
        tracemalloc.stop()
    yield
    if tracemalloc.is_tracing():
        tracemalloc.stop()


def _run(src: str):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": ""}).value


def test_diag_gc_count_returns_three_gens():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.gc_count()\n'
        '  return to_text(length(unwrap(r)))\n'
        '}\n'
    )
    assert result == "3"


def test_diag_object_count_nonzero():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.object_count()\n'
        '  n = unwrap(r)\n'
        '  if n > 0 { return "positive" }\n'
        '  return "zero"\n'
        '}\n'
    )
    assert result == "positive"


def test_diag_thread_count_at_least_one():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.thread_count()\n'
        '  n = unwrap(r)\n'
        '  if n >= 1 { return "ok" }\n'
        '  return "bug"\n'
        '}\n'
    )
    assert result == "ok"


def test_diag_tracemalloc_start_then_snapshot_returns_rows():
    result = _run(
        'entry main(input: Text) {\n'
        '  perform diag.tracemalloc_start(10)\n'
        '  // allocate something traceable in the AIL runtime\n'
        '  buf = repeat_text("x", 4096)\n'
        '  r = perform diag.tracemalloc_snapshot(5)\n'
        '  rows = unwrap(r)\n'
        '  perform diag.tracemalloc_stop()\n'
        '  return to_text(length(rows))\n'
        '}\n'
        'pure fn repeat_text(s: Text, n: Number) -> Text {\n'
        '  out = ""\n'
        '  for i in range(0, n) { out = out + s }\n'
        '  return out\n'
        '}\n'
    )
    # snapshot returns up to top_n=5; allocations vary by Python
    # build, but at least one row should always be present.
    assert int(result) >= 1


def test_diag_tracemalloc_snapshot_without_start_errors():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.tracemalloc_snapshot(5)\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "should not get here"\n'
        '}\n'
    )
    assert result == "tracemalloc_not_started"


def test_diag_tracemalloc_stop_idempotent():
    # Calling stop when not tracing must not raise.
    result = _run(
        'entry main(input: Text) {\n'
        '  a_r = perform diag.tracemalloc_stop()\n'
        '  b_r = perform diag.tracemalloc_stop()\n'
        '  a = unwrap(a_r)\n'
        '  b = unwrap(b_r)\n'
        '  return join([to_text(a), "|", to_text(b)], "")\n'
        '}\n'
    )
    assert result == "true|true"
