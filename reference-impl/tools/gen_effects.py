"""gen_effects — codegen + static-gate tooling for canonical effect / builtin surfaces.

Reads the two canonical sources of truth:
  - spec/effects.canonical.yaml   (cycle 10, D7 doctrine)
  - spec/builtins.canonical.yaml  (cycle 11, D8 doctrine)

Phase 1 scaffolding (사이클 11 Tekton anchor). Provides:
  1. typed loaders for both yaml surfaces
  2. drift verifier — bidirectional static gate (RFC §4):
       yaml entry      ⊆ executor dispatch  (no dead spec)
       executor entry  ⊆ yaml entry         (no phantom dispatch)
  3. registry emitter — a yaml-derived python module the executor can
     import once Phase 1 dispatch migration lands (Telos lane).

The dispatch swap itself (replacing the hand-written effect table in
reference-impl/ail/runtime/executor.py with yaml-driven dispatch) is
Telos's Phase 1 land. This tool is the scaffolding it consumes.

Usage:
    python -m tools.gen_effects verify    # exit 1 on drift
    python -m tools.gen_effects emit-py   # write effects_registry.py
    python -m tools.gen_effects dump      # print parsed structures
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:
    sys.stderr.write(
        "gen_effects: PyYAML is required. Install with: pip install PyYAML>=6.0\n"
    )
    raise SystemExit(2) from e


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EFFECTS_YAML = REPO_ROOT / "spec" / "effects.canonical.yaml"
BUILTINS_YAML = REPO_ROOT / "spec" / "builtins.canonical.yaml"


@dataclass(frozen=True)
class EffectSpec:
    name: str
    tier: str  # "core" | "substrate"
    signature: str
    determinism: str  # replayable | replayable_with_seed | ledger | approval_record | external
    side_effect: str
    capabilities: tuple[str, ...]
    since: str


@dataclass(frozen=True)
class BuiltinSpec:
    name: str
    surface: str  # "function_call"
    signature: str
    determinism: str  # pure | replayable | external_input
    capabilities: tuple[str, ...]
    since: str


@dataclass
class DriftReport:
    yaml_only_effects: list[str] = field(default_factory=list)
    runtime_only_effects: list[str] = field(default_factory=list)
    yaml_only_builtins: list[str] = field(default_factory=list)
    runtime_only_builtins: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not any(
            (
                self.yaml_only_effects,
                self.runtime_only_effects,
                self.yaml_only_builtins,
                self.runtime_only_builtins,
            )
        )

    def as_dict(self) -> dict[str, list[str]]:
        return asdict(self)


def load_effects(path: Path = EFFECTS_YAML) -> list[EffectSpec]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    out: list[EffectSpec] = []
    for entry in raw:
        out.append(
            EffectSpec(
                name=entry["name"],
                tier=entry["tier"],
                signature=entry["signature"],
                determinism=entry["determinism"],
                side_effect=entry["side_effect"],
                capabilities=tuple(entry.get("capabilities", [])),
                since=str(entry["since"]),
            )
        )
    return out


def load_builtins(path: Path = BUILTINS_YAML) -> list[BuiltinSpec]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    out: list[BuiltinSpec] = []
    for entry in raw:
        out.append(
            BuiltinSpec(
                name=entry["name"],
                surface=entry["surface"],
                signature=entry["signature"],
                determinism=entry["determinism"],
                capabilities=tuple(entry.get("capabilities", [])),
                since=str(entry["since"]),
            )
        )
    return out


# Effects the executor exposes but the canonical yaml intentionally does
# not track yet (legacy / lifecycle / single-token convenience). Removing
# the exception means the entry must be added to effects.canonical.yaml
# in the same PR that introduces the dispatch.
_YAML_EXEMPT_EFFECTS: frozenset[str] = frozenset({
    "human_ask",          # legacy alias of human.* family
    "ask_human",          # legacy alias of human.* family
    "log",                # single-token log effect; spec-level log.*
                          # surface is planned for a follow-up RFC
    "inherit_testament",  # Physis lifecycle hook, not a regular effect
})


def discover_runtime_effects() -> set[str]:
    """Read the authoritative `ALLOWED_EFFECTS` frozenset from the executor.

    The executor uses a single registry (`ALLOWED_EFFECTS`) as the
    gate for `perform`. Parsing the literal directly avoids the false
    positives a naive string scrape would catch (`ail.identity` git
    config key, `schedule.json` filename, etc).

    Returns the registry minus `_YAML_EXEMPT_EFFECTS`.
    """
    executor_path = REPO_ROOT / "reference-impl" / "ail" / "runtime" / "executor.py"
    if not executor_path.exists():
        return set()
    src = executor_path.read_text(encoding="utf-8")
    import re

    m = re.search(
        r"ALLOWED_EFFECTS\s*:\s*frozenset\[str\]\s*=\s*frozenset\(\s*\{([^}]+)\}\s*\)",
        src,
        re.DOTALL,
    )
    if not m:
        return set()
    block = m.group(1)
    return {tok for tok in re.findall(r'"([^"]+)"', block)} - _YAML_EXEMPT_EFFECTS


def discover_runtime_builtins() -> set[str]:
    """Enumerate builtins dispatched by name == "<builtin>" branches.

    Same caveat as discover_runtime_effects — scaffolding-grade scrape.
    """
    executor_path = REPO_ROOT / "reference-impl" / "ail" / "runtime" / "executor.py"
    if not executor_path.exists():
        return set()
    src = executor_path.read_text(encoding="utf-8")
    import re

    pat = re.compile(r'if name == "(crypto_[a-z0-9_]+)"')
    return set(pat.findall(src))


def verify() -> DriftReport:
    effects = {e.name for e in load_effects()}
    builtins = {b.name for b in load_builtins()}
    rt_effects = discover_runtime_effects()
    rt_builtins = discover_runtime_builtins()

    report = DriftReport(
        yaml_only_effects=sorted(effects - rt_effects),
        runtime_only_effects=sorted(rt_effects - effects),
        yaml_only_builtins=sorted(builtins - rt_builtins),
        runtime_only_builtins=sorted(rt_builtins - builtins),
    )
    return report


def emit_python_registry(out_path: Path) -> None:
    """Emit a yaml-derived python module that the executor can import.

    The file is intentionally regen-safe: a header sentinel makes the
    target detectable, and the body is pure data — no Python logic.
    """
    effects = load_effects()
    builtins_ = load_builtins()
    payload = {
        "effects": [asdict(e) | {"capabilities": list(e.capabilities)} for e in effects],
        "builtins": [asdict(b) | {"capabilities": list(b.capabilities)} for b in builtins_],
    }
    body = (
        '"""Auto-generated by tools/gen_effects.py. Do not edit by hand."""\n'
        "# yaml-derived registry — regenerate with: python -m tools.gen_effects emit-py\n"
        "\n"
        f"EFFECTS = {json.dumps(payload['effects'], indent=4, ensure_ascii=False)}\n"
        "\n"
        f"BUILTINS = {json.dumps(payload['builtins'], indent=4, ensure_ascii=False)}\n"
    )
    out_path.write_text(body, encoding="utf-8")


def _cmd_verify(_: argparse.Namespace) -> int:
    report = verify()
    if report.clean:
        print("OK — yaml ↔ runtime 1:1 정합 (effects + builtins)")
        return 0
    print("DRIFT detected:")
    print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
    return 1


def _cmd_emit_py(args: argparse.Namespace) -> int:
    out = Path(args.out) if args.out else REPO_ROOT / "reference-impl" / "ail" / "runtime" / "effects_registry.py"
    emit_python_registry(out)
    try:
        rel = out.relative_to(REPO_ROOT)
        print(f"wrote {rel}")
    except ValueError:
        print(f"wrote {out}")
    return 0


def _cmd_dump(_: argparse.Namespace) -> int:
    effects = load_effects()
    builtins_ = load_builtins()
    print(f"effects: {len(effects)}")
    for e in effects:
        print(f"  [{e.tier}] {e.name} :: {e.signature}")
    print(f"builtins: {len(builtins_)}")
    for b in builtins_:
        print(f"  [{b.surface}] {b.name} :: {b.signature}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gen_effects", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify", help="bidirectional yaml ↔ runtime drift check (exit 1 on drift)")
    p_emit = sub.add_parser("emit-py", help="emit a python registry module from yaml")
    p_emit.add_argument("--out", help="output path (default: ail/runtime/effects_registry.py)")
    sub.add_parser("dump", help="print parsed yaml entries")
    args = parser.parse_args(argv)

    handlers = {
        "verify": _cmd_verify,
        "emit-py": _cmd_emit_py,
        "dump": _cmd_dump,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
