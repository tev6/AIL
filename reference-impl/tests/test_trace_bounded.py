"""Regression test for v1.75.1 — `Trace.entries` is bounded by default.

Stoa OOM RCA (cycle 13, AIL `trace.py:45`) traced 3.9 MB / 35k+
calls of unbounded list growth on a 1-minute cold-start tracemalloc
snapshot. The hotfix replaces the list with a `collections.deque`
capped at 10,000 entries by default. This test pins the cap (and
the `AIL_TRACE_UNBOUNDED=1` escape hatch) so the leak cannot come
back silently.
"""
from __future__ import annotations

import collections

import pytest

from ail.runtime.trace import Trace


def test_trace_entries_bounded_by_default(monkeypatch):
    """Default cap of 10,000 — appending more evicts the oldest."""
    monkeypatch.delenv("AIL_TRACE_MAX_ENTRIES", raising=False)
    monkeypatch.delenv("AIL_TRACE_UNBOUNDED", raising=False)
    t = Trace()
    assert isinstance(t.entries, collections.deque)
    assert t.entries.maxlen == 10000

    for i in range(10001):
        t.record("k", i=i)

    assert len(t.entries) == 10000
    # Oldest entry is `i=1` because `i=0` was evicted.
    assert t.entries[0].payload == {"i": 1}
    assert t.entries[-1].payload == {"i": 10000}


def test_trace_max_entries_env_overrides_default(monkeypatch):
    monkeypatch.setenv("AIL_TRACE_MAX_ENTRIES", "50")
    monkeypatch.delenv("AIL_TRACE_UNBOUNDED", raising=False)
    t = Trace()
    assert t.entries.maxlen == 50
    for i in range(60):
        t.record("k", i=i)
    assert len(t.entries) == 50
    assert t.entries[0].payload == {"i": 10}


def test_trace_unbounded_env_disables_cap(monkeypatch):
    """Escape hatch for short-lived test/debug runs that need the full
    trace history. No maxlen → unbounded growth (caller's risk)."""
    monkeypatch.setenv("AIL_TRACE_UNBOUNDED", "1")
    monkeypatch.delenv("AIL_TRACE_MAX_ENTRIES", raising=False)
    t = Trace()
    assert isinstance(t.entries, collections.deque)
    assert t.entries.maxlen is None
    for i in range(10001):
        t.record("k", i=i)
    assert len(t.entries) == 10001


def test_trace_to_list_works_on_bounded_deque(monkeypatch):
    """The `to_list()` and `pretty()` paths iterate the deque the
    same as the old list — no surprises for downstream consumers."""
    monkeypatch.delenv("AIL_TRACE_UNBOUNDED", raising=False)
    monkeypatch.delenv("AIL_TRACE_MAX_ENTRIES", raising=False)
    t = Trace()
    t.record("intent_call", name="x")
    t.record("perform", effect="state.read")
    rows = t.to_list()
    assert len(rows) == 2
    assert rows[0]["kind"] == "intent_call"
    assert rows[1]["kind"] == "perform"
    assert "x" == rows[0]["name"]


def test_trace_invalid_max_entries_env_falls_back_to_default(monkeypatch):
    """A malformed AIL_TRACE_MAX_ENTRIES must not crash boot — fall
    back to the 10,000 default."""
    monkeypatch.setenv("AIL_TRACE_MAX_ENTRIES", "not-a-number")
    monkeypatch.delenv("AIL_TRACE_UNBOUNDED", raising=False)
    t = Trace()
    assert t.entries.maxlen == 10000
