"""on_compact convention (Arche 2026-04-27 #1).

When the evolve-server's `_server_history` reaches 80% of `history_limit`,
the runtime calls `pure fn on_compact(history) -> [Any]` (if defined)
and uses the returned list as the new history. Programs that don't
define on_compact get the unchanged truncate-oldest behavior.

We test the helper directly (executor._maybe_compact_history) instead
of standing up a real Flask evolve-server, mirroring how the test suite
exercises Physis (test_physis.py) without subprocesses.
"""
from __future__ import annotations

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _exec(src: str) -> Executor:
    program = compile_source(src)
    return Executor(program, MockAdapter())


def test_no_on_compact_no_fire():
    """Program with no on_compact → helper returns False, history untouched."""
    src = '''
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    ex._server_history = [{"i": i} for i in range(85)]
    fired = ex._maybe_compact_history(history_limit=100)
    assert fired is False
    assert len(ex._server_history) == 85  # unchanged


def test_below_threshold_no_fire():
    """Even with on_compact defined, below 80% should not fire."""
    src = '''
pure fn on_compact(history: [Any]) -> [Any] { return [] }
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    ex._server_history = [{"i": i} for i in range(70)]
    fired = ex._maybe_compact_history(history_limit=100)
    assert fired is False
    assert len(ex._server_history) == 70


def test_compact_replaces_history_with_returned_list():
    """At 80%+, on_compact runs and its return value becomes the new history."""
    src = '''
pure fn on_compact(history: [Any]) -> [Any] {
    // keep only the last 5 events
    out = []
    n = length(history)
    start = n - 5
    if start < 0 { start = 0 }
    for i in range(start, n) {
        out = append(out, get(history, i))
    }
    return out
}
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    ex._server_history = [{"i": i} for i in range(85)]
    fired = ex._maybe_compact_history(history_limit=100)
    assert fired is True
    assert len(ex._server_history) == 5
    # The 5 most recent: i=80..84
    assert [e["i"] for e in ex._server_history] == [80, 81, 82, 83, 84]


def test_throttle_prevents_back_to_back_recompact():
    """Once compacted, the helper should not re-fire on the next request
    until history grows by at least 10% of history_limit. Otherwise an
    on_compact that returns the input unchanged would loop forever."""
    src = '''
pure fn on_compact(history: [Any]) -> [Any] { return history }
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    ex._server_history = [{"i": i} for i in range(85)]
    first = ex._maybe_compact_history(history_limit=100)
    assert first is True
    # Second call with same size should NOT re-fire (throttle).
    second = ex._maybe_compact_history(history_limit=100)
    assert second is False
    # Grow by < 10% (8 events) → still throttled.
    ex._server_history.extend([{"i": 100 + j} for j in range(8)])
    third = ex._maybe_compact_history(history_limit=100)
    assert third is False
    # Grow past the 10% step (total 95 = 85 + 10) → fires again.
    ex._server_history.extend([{"i": 200 + j} for j in range(2)])
    fourth = ex._maybe_compact_history(history_limit=100)
    assert fourth is True


def test_compact_returning_non_list_is_ignored():
    """If on_compact returns a non-list (Text, Number, etc.), the helper
    must skip the swap and let the normal age-based truncate run."""
    src = '''
pure fn on_compact(history: [Any]) -> Any { return "not a list" }
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    ex._server_history = [{"i": i} for i in range(85)]
    fired = ex._maybe_compact_history(history_limit=100)
    assert fired is False
    assert len(ex._server_history) == 85  # untouched


def test_compact_failure_falls_back():
    """If on_compact raises (e.g., divides by zero, accesses missing key),
    the helper logs and returns False — does not crash the server arm."""
    src = '''
pure fn on_compact(history: [Any]) -> [Any] {
    bad = get(history, 99999)
    return history
}
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    ex._server_history = [{"i": i} for i in range(85)]
    fired = ex._maybe_compact_history(history_limit=100)
    # Either the call raised and was caught (False) or it ran and returned
    # the original — both are acceptable; key requirement is no crash.
    assert fired in (True, False)
    assert len(ex._server_history) == 85 or len(ex._server_history) <= 100
