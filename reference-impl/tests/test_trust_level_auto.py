"""Trust-level auto + intent is_safe (Arche 2026-04-27 #3).

When active context has `trust_level: "auto"`, every `perform` (except
human.approve) consults `intent is_safe(plan: Text) -> Text`. The
intent's text verdict drives the gate:

- "allow" / "safe" → run perform, no further check
- "deny" / "unsafe" → return Result-error, perform does NOT fire
- "ask" / "review" → escalate to human.approve

If `is_safe` is undefined, auto degrades to "allow" (no gate). If the
intent raises, fall back to "ask" (conservative).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter, ModelResponse


class ScriptedAdapter(MockAdapter):
    def __init__(self, scripts):
        super().__init__()
        self.scripts = scripts
        self.calls = []

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None):
        name = context.get("_intent_name", "")
        self.calls.append(name)
        if name in self.scripts:
            value, conf = self.scripts[name]
            return ModelResponse(value=value, confidence=conf,
                                 model_id="scripted", raw={})
        return ModelResponse(value=f"[no script {name}]", confidence=0.5,
                             model_id="scripted", raw={})


def _run(src: str, adapter):
    program = compile_source(src)
    ex = Executor(program, adapter)
    return ex.run_entry({"input": ""}).value


@pytest.fixture()
def approval_dir(tmp_path, monkeypatch):
    d = tmp_path / "approvals"
    d.mkdir()
    monkeypatch.setenv("AIL_APPROVAL_DIR", str(d))
    return d


def _decide_after(approval_dir: Path, decision: str, delay_s: float = 0.1):
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
        path.write_text(json.dumps(data), encoding="utf-8")
    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t


SRC_AUTO = '''
context autonomous extends default {
    trust_level: "auto"
}
intent is_safe(plan: Text) -> Text {
    goal: "evaluate if this action is safe"
}
entry main(input: Text) {
    with context autonomous: {
        r = perform clock.now("unix")
        if is_error(r) { return "DENIED" }
        return "RAN"
    }
}
'''


def test_auto_allow_runs_perform():
    adapter = ScriptedAdapter({"is_safe": ("allow", 0.95)})
    out = _run(SRC_AUTO, adapter)
    assert out == "RAN"
    assert "is_safe" in adapter.calls


def test_auto_deny_blocks_perform():
    adapter = ScriptedAdapter({"is_safe": ("deny", 0.95)})
    out = _run(SRC_AUTO, adapter)
    assert out == "DENIED"
    assert adapter.calls.count("is_safe") == 1


def test_auto_ask_escalates_to_human_approve(approval_dir):
    _decide_after(approval_dir, "approved")
    adapter = ScriptedAdapter({"is_safe": ("ask", 0.95)})
    out = _run(SRC_AUTO, adapter)
    assert out == "RAN"


def test_auto_ask_then_user_declines(approval_dir):
    _decide_after(approval_dir, "declined")
    adapter = ScriptedAdapter({"is_safe": ("ask", 0.95)})
    out = _run(SRC_AUTO, adapter)
    assert out == "DENIED"


def test_auto_without_is_safe_acts_like_allow():
    """No is_safe defined → auto degrades to no-gate. Otherwise every
    perform without an is_safe in scope would lock up."""
    src = '''
context autonomous extends default {
    trust_level: "auto"
}
entry main(input: Text) {
    with context autonomous: {
        perform clock.now("unix")
        return "RAN"
    }
}
'''
    out = _run(src, MockAdapter())
    assert out == "RAN"


def test_auto_unknown_verdict_falls_back_to_ask(approval_dir):
    """If is_safe returns gibberish, runtime takes the conservative
    path = ask the human."""
    _decide_after(approval_dir, "approved")
    adapter = ScriptedAdapter({"is_safe": ("???", 0.5)})
    out = _run(SRC_AUTO, adapter)
    assert out == "RAN"


def test_auto_does_not_call_is_safe_for_human_approve(approval_dir):
    """Explicit human.approve inside auto mode must NOT round-trip
    through is_safe (would double-up the gate and cost a model call)."""
    src = '''
context autonomous extends default {
    trust_level: "auto"
}
intent is_safe(plan: Text) -> Text {
    goal: "evaluate"
}
entry main(input: Text) {
    with context autonomous: {
        r = perform human.approve("plan")
        if is_error(r) { return "D" }
        return "A"
    }
}
'''
    _decide_after(approval_dir, "approved")
    adapter = ScriptedAdapter({"is_safe": ("deny", 0.95)})
    out = _run(src, adapter)
    # human.approve is bypassed by the trust gate skip, so the user
    # decision actually goes through. is_safe must NOT have been called.
    assert out == "A"
    assert "is_safe" not in adapter.calls
