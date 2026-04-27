"""deny-first effect policy (Arche 2026-04-27 #4, ergon).

Behavioral guarantees:

1. Unknown effect → Result-error, NOT RuntimeError. Programs can
   `attempt` / `is_error` around it.
2. Known effect → runs as before (regression).
3. Context `deny_effects: [Text]` → additive deny that overrides any
   permission elsewhere. Strictest-wins across the active context
   stack: once any frame denies, every inner scope inherits.
4. deny beats trust_level — even if `is_safe` would say "allow", a
   `deny_effects` entry blocks.
5. The runtime never crashes on a malformed perform — it returns a
   structured Result.
"""
from __future__ import annotations

import pytest

from ail import compile_source
from ail.runtime.executor import Executor, ALLOWED_EFFECTS
from ail.runtime.model import MockAdapter, ModelResponse


def _run(src: str, adapter=None):
    program = compile_source(src)
    ex = Executor(program, adapter or MockAdapter())
    return ex.run_entry({"input": ""}).value


def test_unknown_effect_is_result_error_not_crash():
    src = '''
entry main(input: Text) {
    r = perform totally.fake.effect("hi")
    if is_error(r) { return "DENIED:" + unwrap_error(r) }
    return "RAN"
}
'''
    out = _run(src)
    assert out.startswith("DENIED:")
    assert "deny-first" in out
    assert "totally.fake.effect" in out


def test_known_effect_still_runs():
    """Regression: a name in ALLOWED_EFFECTS goes through normally."""
    src = '''
entry main(input: Text) {
    r = perform clock.now("unix")
    if is_error(r) { return "ERR" }
    return "OK"
}
'''
    assert _run(src) == "OK"


def test_context_deny_effects_blocks_known_effect():
    """Even though clock.now is in ALLOWED_EFFECTS, an active context
    that lists it in deny_effects blocks it."""
    src = '''
context locked extends default {
    deny_effects: ["clock.now"]
}
entry main(input: Text) {
    with context locked: {
        r = perform clock.now("unix")
        if is_error(r) { return "DENIED" }
        return "RAN"
    }
}
'''
    out = _run(src)
    assert out == "DENIED"


def test_deny_outside_context_does_not_apply():
    """deny_effects only applies inside `with context`."""
    src = '''
context locked extends default {
    deny_effects: ["clock.now"]
}
entry main(input: Text) {
    // not inside with context — no deny in scope
    r = perform clock.now("unix")
    if is_error(r) { return "ERR" }
    return "OK"
}
'''
    assert _run(src) == "OK"


def test_deny_is_additive_across_nested_contexts():
    """Inner context cannot loosen an outer deny — strictest wins."""
    src = '''
context outer extends default {
    deny_effects: ["clock.now"]
}
context inner extends outer {
    note: "inner is silent on deny_effects"
}
entry main(input: Text) {
    with context outer: {
        with context inner: {
            r = perform clock.now("unix")
            if is_error(r) { return "DENIED" }
            return "RAN"
        }
    }
}
'''
    out = _run(src)
    assert out == "DENIED"


def test_deny_beats_trust_level_auto_allow():
    """trust_level=auto + is_safe → 'allow' should still NOT permit a
    deny_effects-listed effect. Deny is strictest, runs first."""
    class S(MockAdapter):
        def invoke(self, *, goal, constraints, context, inputs, **kw):
            if context.get("_intent_name") == "is_safe":
                return ModelResponse(
                    value="allow", confidence=0.95,
                    model_id="s", raw={})
            return ModelResponse(value="?", confidence=0.5,
                                 model_id="s", raw={})

    src = '''
context locked extends default {
    trust_level: "auto"
    deny_effects: ["clock.now"]
}
intent is_safe(plan: Text) -> Text { goal: "evaluate" }
entry main(input: Text) {
    with context locked: {
        r = perform clock.now("unix")
        if is_error(r) { return "DENIED" }
        return "RAN"
    }
}
'''
    out = _run(src, S())
    assert out == "DENIED"
    # is_safe should NOT have been consulted — deny was decided earlier.
    # (But we don't assert on that here since the gate may still run
    # for telemetry. Behavior contract is: result = deny.)


def test_allowed_effects_set_is_explicit():
    """Sanity: ALLOWED_EFFECTS is a frozenset of known names — nothing
    in it should be a typo. Spot-check a few known entries."""
    for required in ("log", "http.get", "file.read", "clock.now",
                     "human.approve", "image.embed"):
        assert required in ALLOWED_EFFECTS, \
            f"missing from ALLOWED_EFFECTS: {required}"
    # And nothing obviously unsafe defaults in by accident
    for forbidden in ("os.system", "shell.exec", "process.kill"):
        assert forbidden not in ALLOWED_EFFECTS
