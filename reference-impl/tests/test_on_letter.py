"""on_letter lifecycle hook (Arche 2026-04-29).

7th lifecycle hook. Fires when the agent's evolve server receives
POST /inbox + a JSON Stoa letter envelope (body has `from` and `id`).
The runtime auto-responds 200 OK and skips the user's `when` block,
so agents can react to letters without writing HTTP routing.

Same convention pattern as the other lifecycle hooks — fn-name lookup,
absent → fall through, raised → log + skip.
"""
from ail import compile_source, MockAdapter
from ail.runtime.executor import Executor, ConfidentValue


def _exec(src: str) -> Executor:
    return Executor(compile_source(src), MockAdapter())


def test_on_letter_dispatches_via_lifecycle_helper():
    src = '''
fn on_letter(letter: Any) -> Text {
    return get(letter, "from")
}
entry main(input: Text) { return "ok" }
'''
    ex = _exec(src)
    letter = {"id": "msg_1", "from": "arche", "to": "ergon",
              "title": "hi", "content": "hello"}
    cv = ex._invoke_lifecycle_hook("on_letter", [ConfidentValue(letter, 1.0)])
    assert cv is not None
    assert cv.value == "arche"


def test_on_letter_absent_is_noop():
    src = 'entry main(input: Text) { return "ok" }'
    ex = _exec(src)
    assert ex._invoke_lifecycle_hook("on_letter", []) is None


def test_on_letter_failure_is_swallowed():
    """A broken on_letter must not kill the request loop. We trigger an
    error by invoking with a wrong-arity arg list — the body expects
    `letter` but we pass nothing."""
    src = '''
fn on_letter(letter: Any) -> Text {
    return get(letter, "from")
}
entry main(input: Text) { return "ok" }
'''
    ex = _exec(src)
    # Pass no args — `letter` will be unbound and `get(letter, "from")`
    # will raise inside the body. The helper must swallow.
    result = ex._invoke_lifecycle_hook("on_letter", [])
    assert result is None


def test_self_letter_pattern_via_record_inspection():
    """The hook receives the letter as a Record. Self-letters are just
    letters where from == to — same dispatch path. We verify the hook
    sees the right values; persistence (state.write) is covered elsewhere."""
    src = '''
fn on_letter(letter: Any) -> Any {
    return [
        ["from", get(letter, "from")],
        ["to", get(letter, "to")],
        ["self", get(letter, "from") == get(letter, "to")]
    ]
}
entry main(input: Text) { return "ok" }
'''
    ex = _exec(src)
    self_letter = {"id": "self_1", "from": "ergon", "to": "ergon",
                   "content": "remember to handle X"}
    cv = ex._invoke_lifecycle_hook(
        "on_letter", [ConfidentValue(self_letter, 1.0)])
    rec = dict(cv.value)
    assert rec["from"] == "ergon"
    assert rec["to"] == "ergon"
    assert rec["self"] is True
