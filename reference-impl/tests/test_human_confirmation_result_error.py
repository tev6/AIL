"""Regression test for #22 — `human_confirmation` deny path returns
Result-error (not RuntimeError).

Before fix (`executor.py:689`): declined confirmation raised
`RuntimeError` and tore the executor's `attempt` frame, breaking the
documented Result-shape contract and Go-runtime parity.

After fix: declined confirmation returns the same Result-shape error
that `human.approve` uses on user_decline (executor.py:663-670), so
callers can pattern-match on `ok == false` and program-level
`attempt`/fallback recovers.
"""
from __future__ import annotations

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


_PROG = """\
effect send_post {
    signature: (text: Text) -> Boolean
    authorization: human_confirmation
}

entry main(input: Text) {
    r = perform send_post(input)
    return r
}
"""


def _run_with_ask(answer: bool):
    program = compile_source(_PROG)
    ex = Executor(
        program,
        MockAdapter(),
        ask_human=lambda question, expect="text": answer,
    )
    return ex.run_entry({"input": "hello"})


def test_human_confirmation_decline_returns_result_error():
    cv = _run_with_ask(False)
    val = cv.value
    assert isinstance(val, dict), f"expected Result dict, got {type(val)}: {val!r}"
    assert val.get("_result") is True
    assert val.get("ok") is False
    assert "send_post" in val.get("error", "")
    assert "denied" in val.get("error", "").lower()


def test_human_confirmation_decline_does_not_raise():
    try:
        _run_with_ask(False)
    except RuntimeError as e:
        raise AssertionError(
            f"declined human_confirmation must not raise RuntimeError "
            f"(got: {e!r})"
        )


def test_human_confirmation_approve_runs_effect():
    cv = _run_with_ask(True)
    val = cv.value
    # With no effect implementation registered, builtin dispatch returns
    # a Result-shape; the relevant invariant is that the deny path is
    # gone, not that an unimplemented effect succeeds. Either ok=True or
    # ok=False is fine — what must NOT happen is a RuntimeError.
    assert isinstance(val, dict)
    assert val.get("_result") is True
