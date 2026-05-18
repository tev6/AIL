"""Tests for native-layer diag.* effects — malloc_stats + smaps_summary.

These two effects decompose the tracemalloc-top10-vs-VmRSS gap by
asking glibc and /proc/self/smaps directly. Both are Linux-only;
the macOS/Windows path must return Result-error so the platform
gap surfaces instead of producing empty rows.
"""
from __future__ import annotations

import os
import platform

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str) -> object:
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": ""}).value


_IS_LINUX = platform.system() == "Linux"


@pytest.mark.skipif(not _IS_LINUX, reason="Linux-only effect")
def test_diag_malloc_stats_on_linux_returns_record():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.malloc_stats()\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  rec = unwrap(r)\n'
        '  return join([\n'
        '    to_text(get(rec, "arena")), "|",\n'
        '    to_text(get(rec, "uordblks")), "|",\n'
        '    to_text(get(rec, "fordblks"))\n'
        '  ], "")\n'
        '}\n'
    )
    # On glibc >= 2.33 we get real numbers; on older glibc we get
    # the "lacks mallinfo2" error string. Both are acceptable; we
    # only assert that the call did not raise.
    assert isinstance(result, str)


@pytest.mark.skipif(_IS_LINUX, reason="non-Linux only")
def test_diag_malloc_stats_non_linux_returns_unsupported():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.malloc_stats()\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "should not get here"\n'
        '}\n'
    )
    assert result == "malloc_stats_unsupported"


@pytest.mark.skipif(not _IS_LINUX, reason="Linux-only effect")
def test_diag_smaps_summary_returns_kb_fields():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.smaps_summary()\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  rec = unwrap(r)\n'
        '  return join([\n'
        '    to_text(get(rec, "rss_anon_kb")), "|",\n'
        '    to_text(get(rec, "rss_file_kb")), "|",\n'
        '    to_text(get(rec, "heap_kb")), "|",\n'
        '    to_text(get(rec, "stack_kb"))\n'
        '  ], "")\n'
        '}\n'
    )
    parts = result.split("|")
    assert len(parts) == 4
    # Every field is a non-negative integer.
    for v in parts:
        assert int(v) >= 0
    # At least one bucket should be nonzero on any real Linux process.
    assert any(int(v) > 0 for v in parts)


@pytest.mark.skipif(_IS_LINUX, reason="non-Linux only")
def test_diag_smaps_summary_no_proc_returns_unsupported():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = perform diag.smaps_summary()\n'
        '  if is_error(r) { return unwrap_error(r) }\n'
        '  return "should not get here"\n'
        '}\n'
    )
    assert result == "smaps_unsupported"
