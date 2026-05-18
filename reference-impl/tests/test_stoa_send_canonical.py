"""Byte-for-byte test of the pure-AIL canonical_letter mirror.

The pure-AIL agent demo RFC (`docs/proposals/pure-ail-agent-demo.md`)
retires the Python sidecar's canonical layer by reimplementing it as
a pure fn in `agents/tekton/stoa_send.ail`. This test pins that
reimplementation to byte-equality with the Python sidecar's
`stoa_cli.canonical_letter` for a stress fixture that covers every
RFC-001 §6.1 escape (backslash / pipe / semicolon / colon) inside
each field of the envelope.

If this test fails after either side is touched, the AIL agent's
signed envelopes will be rejected by the Stoa server's signature
check. There is no graceful failure mode — they must match byte by
byte.
"""
from __future__ import annotations

import sys
from pathlib import Path

# stoa-cli is repo tooling, not a pip package. Add its directory
# to sys.path so the test can import the canonical reference.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_STOA_CLI_DIR = _REPO_ROOT / "community-tools" / "stoa-cli"
if str(_STOA_CLI_DIR) not in sys.path:
    sys.path.insert(0, str(_STOA_CLI_DIR))

from stoa_cli import canonical_letter as py_canonical_letter

from ail.parser import parse
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _ail_canonical(envelope: dict) -> str:
    """Run the AIL canonical_letter via a driver entry that imports
    the pure fn from `agents/tekton/stoa_send.ail`. Returns the
    resulting Text exactly as the AIL program produced it."""
    driver = _REPO_ROOT / "agents" / "tekton" / \
        "stoa_send_canonical_driver.ail"
    source = driver.read_text(encoding="utf-8")
    program = parse(source)
    # project_root must be the driver's own directory — the AIL
    # relative-import resolver pins `./x` to importing_from and
    # rejects anything that climbs out of it. Driver and the
    # imported stoa_send.ail live in the same directory for this
    # reason; see RFC docs/proposals/pure-ail-agent-demo.md §6.
    ex = Executor(program, MockAdapter(), project_root=driver.parent)
    fr = envelope["from"]
    # Pack fixture inputs into the entry's `input` parameter as
    # newline-separated fields — the driver pulls them apart so the
    # test can drive the same fn body the agent will call. Order
    # matches the entry signature.
    payload = "\n".join([
        fr["name"], fr["address"],
        envelope["to"][0]["name"], envelope["to"][0]["address"],
        envelope["content"],
        envelope["created_at"],
        envelope["nonce"],
    ])
    return ex.run_entry({"input": payload}).value


_STRESS_ENVELOPE = {
    "from": {
        "name": "telos",
        "address": "https://ail-stoa.up.railway.app/inbox/telos",
    },
    "to": [{
        "name": "arche",
        "address": "https://ail-stoa.up.railway.app/inbox/arche",
    }],
    "content": "test|content;with:special\\chars",
    "created_at": "2026-05-18T05:00:00Z",
    "nonce": "deadbeefcafef00d",
}


def test_canonical_letter_matches_python_sidecar_byte_for_byte():
    ail_out = _ail_canonical(_STRESS_ENVELOPE)
    py_out = py_canonical_letter(_STRESS_ENVELOPE)
    assert ail_out == py_out, (
        f"\n  AIL: {ail_out!r}\n  Py : {py_out!r}\n"
        "Pure-AIL canonical_letter must match the Python sidecar "
        "byte for byte — a divergence will make signed AIL "
        "envelopes fail the server's signature check."
    )


def test_canonical_letter_escape_order_matters():
    """The escape order in RFC-001 §6.1 is fixed: \\ first, then |,
    then ;, then :. If the AIL implementation reorders the chain,
    a payload like `|;:` will get double-escaped on the first step
    and produce a different byte string. This test pins the
    pathological case."""
    env = dict(_STRESS_ENVELOPE)
    env["content"] = "\\|;:"
    ail_out = _ail_canonical(env)
    py_out = py_canonical_letter(env)
    assert ail_out == py_out, (
        f"\n  AIL: {ail_out!r}\n  Py : {py_out!r}"
    )
