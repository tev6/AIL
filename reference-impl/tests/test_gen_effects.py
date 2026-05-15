"""Static gate: yaml ↔ runtime 1:1 (effects + builtins)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.gen_effects import (  # noqa: E402
    load_builtins,
    load_effects,
    verify,
    emit_python_registry,
)


def test_load_effects_nonempty():
    effects = load_effects()
    assert len(effects) > 0
    by_tier = {}
    for e in effects:
        by_tier.setdefault(e.tier, []).append(e)
    assert "core" in by_tier and "substrate" in by_tier
    valid_determinism = {
        "replayable", "replayable_with_seed", "ledger",
        "approval_record", "external",
    }
    for e in effects:
        assert e.determinism in valid_determinism, (e.name, e.determinism)
        assert e.tier in ("core", "substrate"), (e.name, e.tier)
        assert e.signature.startswith("("), (e.name, e.signature)


def test_load_builtins_nonempty():
    builtins_ = load_builtins()
    assert len(builtins_) > 0
    valid_determinism = {"pure", "replayable", "external_input"}
    for b in builtins_:
        assert b.surface == "function_call", (b.name, b.surface)
        assert b.determinism in valid_determinism, (b.name, b.determinism)


def test_no_drift_yaml_vs_runtime():
    """RFC §4 bidirectional static gate (effect-conformance Phase 1)."""
    report = verify()
    assert report.clean, (
        "yaml ↔ runtime drift detected:\n"
        f"  yaml_only_effects:    {report.yaml_only_effects}\n"
        f"  runtime_only_effects: {report.runtime_only_effects}\n"
        f"  yaml_only_builtins:   {report.yaml_only_builtins}\n"
        f"  runtime_only_builtins: {report.runtime_only_builtins}\n"
        "Either add the missing entry to spec/*.canonical.yaml or remove\n"
        "the orphan from executor.py. See docs/proposals/effect-conformance.md."
    )


def test_emit_python_registry(tmp_path):
    out = tmp_path / "effects_registry.py"
    emit_python_registry(out)
    src = out.read_text(encoding="utf-8")
    assert "Auto-generated" in src
    assert "EFFECTS = " in src
    assert "BUILTINS = " in src
    namespace: dict = {}
    exec(src, namespace)
    assert isinstance(namespace["EFFECTS"], list)
    assert isinstance(namespace["BUILTINS"], list)
    assert len(namespace["EFFECTS"]) == len(load_effects())
    assert len(namespace["BUILTINS"]) == len(load_builtins())
