"""perform-as-expression (Telos's "perform nested bug" — 2026-04-26).

Telos reported that `save_messages` in `stoa/server.ail` returned 201
but never wrote the file. The original signature ended with:

    return perform file.write(get_data_file(), unwrap(r))

He traced the symptom along the call chain and concluded that
`perform env.read` inside a nested fn returned a different value than
when called directly — i.e., a scope/dispatch bug. The hypothesis was
plausible but wrong. The actual cause was parser-level:

    `perform` was not recognized in expression position. The parser
    silently consumed only the bare identifier `perform` (interpreted
    as a symbol per AIL's identifier-fallback semantics) and stopped.
    The effect call never fired. The function returned the literal
    string "perform". `is_error("perform")` is False, so the caller
    happily reported success.

Fix (2026-04-27, ergon): parse_primary now recognizes `perform` as
expression-position effect call, producing a PerformExpr that the
executor already knew how to evaluate. The construct
`return perform x.y(...)` now works as authors expect.

These tests pin both the formerly broken construct and adjacent
expression positions (function args, `if` condition, etc.).
"""
from __future__ import annotations

import os
import tempfile

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str, inp: str = ""):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": inp}).value


def test_return_perform_runs_effect_and_returns_result():
    """The original Telos repro: `return perform file.write(...)`.

    Pre-fix: returns the string "perform", file untouched.
    Post-fix: returns Result-ok, file written.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tf:
        target = tf.name
    try:
        out = _run(f'''
fn write_via(path: Text, content: Text) -> Any {{
    return perform file.write(path, content)
}}
entry main(input: Text) {{
    r = write_via("{target}", "hello")
    return to_text(r)
}}
''')
        assert "perform" != out  # not the bare string
        assert "ok" in out  # Result-ok dict surfaces
        assert os.path.exists(target)
        assert open(target).read() == "hello"
    finally:
        if os.path.exists(target):
            os.unlink(target)


def test_perform_as_argument_to_function():
    """perform in a call argument position — also was broken pre-fix."""
    out = _run('''
entry main(input: Text) {
    // perform result fed directly into to_text — was broken pre-fix
    return to_text(perform clock.now("unix"))
}
''')
    # clock.now returns an ISO-8601 timestamp; we just check it's not
    # the bare string "perform" (which is what the bug produced).
    assert out != "perform"
    assert len(out) >= 4  # any sensible timestamp is longer


def test_perform_in_if_condition():
    """Effect result tested directly in an `if` predicate."""
    out = _run('''
entry main(input: Text) {
    r = perform env.read("DEFINITELY_NOT_SET_99XYZ")
    if is_error(r) {
        return "err"
    }
    return "ok"
}
''')
    assert out == "err"


def test_nested_fn_inheriting_outer_perform_works():
    """The original symptom: nested fn calls perform — same value as
    when called directly. (Always worked in the runtime; the bug was
    in parsing of the surrounding `return perform` form.)"""
    os.environ["AIL_NESTED_TEST_VAR"] = "from-env"
    try:
        out = _run('''
fn inner() -> Text {
    r = perform env.read("AIL_NESTED_TEST_VAR")
    if is_error(r) { return "missing" }
    return unwrap(r)
}
entry main(input: Text) {
    direct_r = perform env.read("AIL_NESTED_TEST_VAR")
    nested = inner()
    return join(["direct=", unwrap(direct_r), " nested=", nested], "")
}
''')
        assert out == "direct=from-env nested=from-env"
    finally:
        os.environ.pop("AIL_NESTED_TEST_VAR", None)
