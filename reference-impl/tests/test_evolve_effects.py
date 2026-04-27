"""Tests for evolve-server infra-layer deny-first (effects: field).

Arche 2026-04-27: deny-first applies at two layers.
- Citizen layer (intent): ALLOWED_EFFECTS or declared effect keyword.
- Infra layer (evolve-server): effects declared in evolve effects field.

These tests verify that:
1. An effect declared in `effects:` is allowed in the server.
2. An effect NOT declared is denied even if it's in ALLOWED_EFFECTS.
3. When `effects:` is absent, fall back to citizen-layer ALLOWED_EFFECTS.
"""
import pytest
from ail.parser.parser import parse
from ail.runtime.executor import Executor
from ail.runtime import MockAdapter


# Minimal evolve-server harness that records calls to a perform without
# actually executing the external effect.
_SERVER_TEMPLATE = """
fn handle(req: Any) -> [Any] {{
    {body}
    return [200, "text/plain", "ok"]
}}

evolve test_srv {{
    listen: 9999
    {effects_field}
    when request_received(req) {{
        handle(req)
    }}
    rollback_on: error_rate > 0.9
    history: keep_last 10
}}
"""


def _parse_and_run_once(code: str) -> dict:
    """Parse code, run the server handler once with a dummy request, return debug log."""
    prog = parse(code)
    ex = Executor(prog, MockAdapter())
    evolve_decl = next(iter(ex.evolves.values()))
    # Manually activate infra-layer as run_server would
    from ail.runtime.executor import ConfidentValue
    declared = getattr(evolve_decl, "effects", None) or []
    ex._server_evolve_effects = set(declared) if declared else None
    # Simulate single request dispatch
    arm = evolve_decl.server_arm
    scope = {arm.req_var: ConfidentValue({}, 1.0)}
    results = []
    original_perform = ex._exec_perform

    def capturing_perform(stmt, s):
        result = original_perform(stmt, s)
        results.append((stmt.effect, result.value))
        return result

    ex._exec_perform = capturing_perform
    try:
        ex._exec_block(arm.body, scope)
    except Exception:
        pass
    return results


def test_declared_effect_allowed():
    """effect in effects: field is permitted (returns ok, not denied)."""
    code = _SERVER_TEMPLATE.format(
        effects_field='effects: [state.write]',
        body='r = perform state.write("k", "v")',
    )
    results = _parse_and_run_once(code)
    # state.write should have been attempted (result may be ok or infra error,
    # but NOT a deny-first error)
    sw = [r for (e, r) in results if e == "state.write"]
    assert sw, "state.write was never performed"
    result = sw[0]
    if isinstance(result, dict):
        assert "deny-first" not in result.get("error", ""), \
            f"state.write was denied: {result}"


def test_undeclared_effect_denied():
    """effect NOT in effects: field is denied even if in ALLOWED_EFFECTS."""
    code = _SERVER_TEMPLATE.format(
        effects_field='effects: [state.write]',
        body='r = perform file.read("x.txt")',
    )
    results = _parse_and_run_once(code)
    fr = [r for (e, r) in results if e == "file.read"]
    assert fr, "file.read was never attempted"
    result = fr[0]
    assert isinstance(result, dict) and "deny-first (infra)" in result.get("error", ""), \
        f"Expected infra deny, got: {result}"


def test_no_effects_field_falls_back_to_allowed_effects():
    """When effects: absent, ALLOWED_EFFECTS applies (citizen-layer behavior)."""
    code = _SERVER_TEMPLATE.format(
        effects_field='',
        body='r = perform state.write("k", "v")',
    )
    results = _parse_and_run_once(code)
    sw = [r for (e, r) in results if e == "state.write"]
    assert sw, "state.write was never performed"
    result = sw[0]
    if isinstance(result, dict):
        # Should NOT get a deny-first error (state.write is in ALLOWED_EFFECTS)
        assert "deny-first" not in result.get("error", ""), \
            f"Unexpected denial: {result}"


def test_effects_field_parsed_correctly():
    """Parser correctly populates EvolveDecl.effects list."""
    code = _SERVER_TEMPLATE.format(
        effects_field='effects: [email.send, file.read, http.respond]',
        body='',
    )
    prog = parse(code)
    from ail.parser.ast import EvolveDecl
    evolve = next(d for d in prog.declarations if isinstance(d, EvolveDecl))
    assert set(evolve.effects) == {"email.send", "file.read", "http.respond"}
