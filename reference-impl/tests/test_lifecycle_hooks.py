"""Lifecycle hooks (Arche 2026-04-28).

Five fn-name conventions on top of evolve servers, dispatched the same
way as on_death / on_compact:

  on_genesis(testament)   — once, before evolve loop. testament is a
                            Result so first-gen and successors share a parser.
  on_birth()              — once, right after on_genesis.
  before_tick(state)      — every request, before the `when` block.
  on_tick(state)          — every request, between before_tick and `when`.
  after_tick(state)       — every request, after the `when` block.

We test helpers directly (no Flask subprocess), mirroring test_on_compact.
"""
from __future__ import annotations

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _exec(src: str) -> Executor:
    return Executor(compile_source(src), MockAdapter())


def test_invoke_absent_hook_is_noop():
    src = 'entry main(x: Text) { return "ok" }'
    ex = _exec(src)
    assert ex._invoke_lifecycle_hook("on_birth", []) is None
    assert ex._invoke_lifecycle_hook("before_tick", []) is None


def test_invoke_present_hook_returns_value():
    src = '''
fn on_birth() -> Text { return "hello" }
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    cv = ex._invoke_lifecycle_hook("on_birth", [])
    assert cv is not None
    assert cv.value == "hello"


def test_hook_failure_is_swallowed_not_raised():
    """A broken hook must not kill the loop — runtime logs and moves on."""
    src = '''
fn before_tick(state: Any) -> Any {
    return get(state, "no_such_key").nope.nope
}
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    # Should not raise even though the body explodes.
    result = ex._invoke_lifecycle_hook("before_tick", [])
    assert result is None


def test_build_tick_state_shape():
    """State record handed to before_tick / on_tick / after_tick contains
    the metrics + a history snapshot."""
    src = 'entry main(x: Text) { return "ok" }'
    ex = _exec(src)
    ex._server_request_count = 4
    ex._server_error_count = 1
    ex._server_history = [{"i": 0}, {"i": 1}]
    ex._active_generation = 7
    state = ex._build_tick_state()
    assert state["request_count"] == 4
    assert state["error_count"] == 1
    assert state["error_rate"] == 0.25
    assert state["generation"] == 7
    assert state["history"] == [{"i": 0}, {"i": 1}]
    # snapshot — mutating returned history must not alias ring buffer
    state["history"].append({"i": 99})
    assert ex._server_history == [{"i": 0}, {"i": 1}]


def test_tick_state_zero_requests_safe():
    src = 'entry main(x: Text) { return "ok" }'
    ex = _exec(src)
    state = ex._build_tick_state()
    assert state["request_count"] == 0
    assert state["error_rate"] == 0.0
    assert state["history"] == []


def test_hook_can_read_state_record():
    """Hook receives the state dict and can extract fields with `get`."""
    src = '''
fn on_tick(state: Any) -> Number { return get(state, "request_count") }
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    from ail.runtime.executor import ConfidentValue
    state = {"request_count": 3, "error_count": 0, "error_rate": 0.0,
             "generation": 1, "history": []}
    cv = ex._invoke_lifecycle_hook("on_tick", [ConfidentValue(state, 1.0)])
    assert cv is not None
    assert cv.value == 3


def test_genesis_testament_result_shape():
    """on_genesis receives a Result — ok=False on first gen, ok=True with
    value on inheritance. Hook can branch via is_error / unwrap."""
    src = '''
fn on_genesis(testament: Any) -> Text {
    if is_error(testament) {
        return "first generation"
    }
    t = unwrap(testament)
    return get(t, "reason")
}
entry main(x: Text) { return "ok" }
'''
    ex = _exec(src)
    from ail.runtime.executor import ConfidentValue
    # Genesis (no predecessor)
    cv1 = ex._invoke_lifecycle_hook("on_genesis", [ConfidentValue(
        {"_result": True, "ok": False, "error": "no testament — genesis"}, 1.0)])
    assert cv1.value == "first generation"
    # Successor
    cv2 = ex._invoke_lifecycle_hook("on_genesis", [ConfidentValue(
        {"_result": True, "ok": True,
         "value": {"reason": "rollback_on fired", "generation": 2}}, 1.0)])
    assert cv2.value == "rollback_on fired"
