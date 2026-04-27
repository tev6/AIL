"""Trust-level gate (Arche 2026-04-27 #2).

Active context with `trust_level: "plan"` causes every `perform` (except
human.approve itself) to auto-route through human.approve. Decline →
Result-error. Default / absent trust_level = current behavior (no
auto-gate).

Tests drive the approval queue from a sibling thread, exactly like
test_human_approve.py.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str, inp: str = ""):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": inp}).value


@pytest.fixture()
def approval_dir(tmp_path, monkeypatch):
    d = tmp_path / "approvals"
    d.mkdir()
    monkeypatch.setenv("AIL_APPROVAL_DIR", str(d))
    return d


def _decide_after(approval_dir: Path, decision: str, reason: str = "",
                  delay_s: float = 0.1):
    def _worker():
        time.sleep(delay_s)
        path = approval_dir / "pending.json"
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if path.is_file():
                break
            time.sleep(0.05)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = decision
        if reason:
            data["reason"] = reason
        path.write_text(json.dumps(data), encoding="utf-8")
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


SRC_PLAN = '''
context cautious extends default {
    trust_level: "plan"
}

entry main(input: Text) {
    with context cautious: {
        r = perform file.write("/tmp/_trust_test_out.txt", "hi")
        if is_error(r) { return "DENIED" }
        return "WROTE"
    }
}
'''

SRC_DEFAULT = '''
entry main(input: Text) {
    r = perform file.write("/tmp/_trust_test_out.txt", "hi")
    if is_error(r) { return "ERR" }
    return "WROTE"
}
'''


def test_plan_mode_approved_lets_effect_run(approval_dir, tmp_path, monkeypatch):
    monkeypatch.setattr("pathlib.Path.write_text",
                        lambda self, *a, **kw: None, raising=True)
    # We can't easily mock file.write; just observe approval gate fires.
    # Use a different effect that doesn't touch fs: state.write via approval.
    src = '''
context cautious extends default {
    trust_level: "plan"
}

entry main(input: Text) {
    with context cautious: {
        perform clock.now("unix")
        return "DONE"
    }
}
'''
    monkeypatch.undo()  # un-patch the write so AIL state.write works
    _decide_after(approval_dir, "approved")
    out = _run(src)
    assert out == "DONE"


def test_plan_mode_declined_returns_result_error(approval_dir):
    src = '''
context cautious extends default {
    trust_level: "plan"
}

entry main(input: Text) {
    with context cautious: {
        r = perform clock.now("unix")
        if is_error(r) { return "DENIED" }
        return "RAN"
    }
}
'''
    _decide_after(approval_dir, "declined", reason="no thanks")
    out = _run(src)
    assert out == "DENIED"


def test_default_mode_no_gate(approval_dir):
    """Without `with context cautious`, perform runs immediately —
    no approve queue interaction."""
    src = '''
entry main(input: Text) {
    perform state.write("k", "v")
    return "RAN"
}
'''
    # No _decide_after — if the gate fired, the test would hang.
    out = _run(src)
    assert out == "RAN"


def test_plan_mode_does_not_double_gate_human_approve(approval_dir):
    """An explicit `human.approve` inside trust_level=plan must not be
    double-gated through another approval — the user would see two
    cards for one intended ask."""
    src = '''
context cautious extends default {
    trust_level: "plan"
}

entry main(input: Text) {
    with context cautious: {
        r = perform human.approve("real plan")
        if is_error(r) { return "DECLINED" }
        return "APPROVED"
    }
}
'''
    _decide_after(approval_dir, "approved")
    out = _run(src)
    assert out == "APPROVED"
