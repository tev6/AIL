"""ail bundle — turn scattered lifecycle .ail files into one evolve-server.

Why this exists (hyun06000 + Arche 2026-04-29 field test):

Humans naturally split work into small files, verify each part, then
combine — *"먼저 부품을 따로 시험하고, 동작하면 합쳐서 배포한다."* But
v1.67/1.68 lifecycle hooks (on_genesis / on_birth / on_tick / on_dying /
on_death) are recognized only as **fn declarations inside one module**
that also has an `evolve` block. So a project written as five separate
`entry main` files isn't deployable, even when each part works.

`ail bundle` closes the gap. Inputs: the scattered files. Output: one
file with the same logic re-shaped as fn-convention hooks plus an
evolve block (with a Physis-default rollback_on). After bundling the
project is deploy-eligible without rewriting any logic.

Default `rollback_on`:

    error_rate > 0.5 or consecutive_failures > 5

This mirrors the scheduler self-throttle (Telos 2026-04-29) — the same
"같은 실수를 반복하지 마라" rule applied at two layers. Arche
2026-04-29 directive: "bundle이 생성하는 evolve 블록의 기본 rollback_on
값을 빈 칸으로 두면 HEAAL 위반이야." This is that default.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Hook fn signatures the runtime recognizes (executor.py:_invoke_lifecycle_hook
# convention dispatch). on_death is `pure fn` per the v0.3 convention; the
# rest can have side effects.
_HOOK_SIGNATURES: dict[str, str] = {
    "on_genesis":  "fn on_genesis(testament: Record) -> Record",
    "on_birth":    "fn on_birth() -> Text",
    "before_tick": "fn before_tick(state: Record) -> Text",
    "on_tick":     "fn on_tick(state: Record) -> Text",
    "after_tick":  "fn after_tick(state: Record) -> Text",
    "on_dying":    "fn on_dying(reason: Text, history: [Record]) -> Text",
    "on_death":    "pure fn on_death(testament: Record) -> Record",
}

# Stable order for emission — same as the runtime invocation order so a
# reader's eye flows top-to-bottom in lifecycle order.
_HOOK_ORDER = [
    "on_genesis", "on_birth", "before_tick",
    "on_tick", "after_tick", "on_dying", "on_death",
]

DEFAULT_ROLLBACK_ON = "error_rate > 0.5 or consecutive_failures > 5"
DEFAULT_LISTEN_PORT = 8090
DEFAULT_SCHEDULE_SECONDS = 60


@dataclass
class BundleResult:
    source: str
    used_files: list[str]
    skipped_files: list[str]
    output_path: Optional[Path]


def hook_name_from_path(p: Path) -> Optional[str]:
    """Map e.g. `on_birth.ail` → `on_birth`. Returns None if not a hook."""
    if p.suffix != ".ail":
        return None
    return p.stem if p.stem in _HOOK_SIGNATURES else None


def _split_entry_main(text: str) -> tuple[str, Optional[str]]:
    """Find `entry main(...) { ... }` and return (text_before, body_inside).

    `body_inside` is None when no entry main was found (entire text is
    "before"). Brace-matching honors nested blocks.
    """
    m = re.search(r"\bentry\s+main\s*\([^)]*\)\s*\{", text)
    if not m:
        return text, None
    pre = text[:m.start()]
    body_start = m.end()
    depth = 1
    i = body_start
    while i < len(text) and depth > 0:
        ch = text[i]
        # Naive — doesn't honor strings/comments — but lifecycle bodies
        # rarely contain raw `{`/`}` in strings; AIL string literals
        # don't support unescaped braces. Good enough for the common case.
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return text, None
    body = text[body_start:i - 1]
    return pre, body.strip("\n")


def _strip_header_comments(text: str) -> str:
    """Drop the leading `// INPUT:` / `# PURPOSE:` lines used as scaffolding
    in standalone files — they're meaningful only when the file *is* a
    program, not when its body becomes a fn body inside a bundle."""
    lines = text.split("\n")
    out_lines: list[str] = []
    leading = True
    for line in lines:
        stripped = line.strip()
        if leading and (
            stripped.startswith("// INPUT:")
            or stripped.startswith("# INPUT:")
            or stripped.startswith("// PURPOSE:")
            or stripped.startswith("# PURPOSE:")
            or stripped == ""
        ):
            if stripped == "" and out_lines and out_lines[-1] != "":
                # collapse runs of blanks into one
                continue
            continue
        leading = False
        out_lines.append(line)
    return "\n".join(out_lines).strip()


def _wrap_body_as_hook(hook: str, body: str) -> str:
    """Wrap an `entry main` body so it becomes a lifecycle hook fn.

    Source files were written with `input: Text` parameter and many
    don't actually use it — but a few do. We inject `input = ""` at the
    top so any straggling reference still resolves cleanly.
    """
    sig = _HOOK_SIGNATURES[hook]
    indented = "\n".join(
        ("    " + line) if line.strip() else line
        for line in body.split("\n")
    )
    return f"{sig} {{\n    input = \"\"\n{indented}\n}}"


def bundle(
    files: list[Path],
    *,
    output: Path,
    listen: int = DEFAULT_LISTEN_PORT,
    schedule_seconds: int = DEFAULT_SCHEDULE_SECONDS,
    rollback_on: str = DEFAULT_ROLLBACK_ON,
) -> BundleResult:
    """Combine scattered lifecycle files into one evolve-server module.

    Files whose stem matches a known hook name (e.g. `on_birth.ail`)
    contribute their `entry main` body as that hook. Top-level
    declarations above `entry main` (intent / pure fn / etc.) are
    preserved as program-level helpers. Files that are not lifecycle
    files are skipped (not silently merged).
    """
    helpers: list[str] = []
    hook_blocks: dict[str, str] = {}
    used: list[str] = []
    skipped: list[str] = []

    for path in files:
        hook = hook_name_from_path(path)
        if hook is None:
            skipped.append(path.name)
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            skipped.append(path.name)
            continue
        pre, body = _split_entry_main(raw)
        if body is None:
            skipped.append(path.name)
            continue
        pre_clean = _strip_header_comments(pre)
        if pre_clean:
            helpers.append(f"// from {path.name}\n{pre_clean}")
        hook_blocks[hook] = _wrap_body_as_hook(hook, body)
        used.append(path.name)

    if not hook_blocks:
        return BundleResult(
            source="", used_files=[], skipped_files=skipped,
            output_path=None,
        )

    parts: list[str] = []
    parts.append(
        "// Bundled by `ail bundle` from: " + ", ".join(used)
    )
    parts.append(
        "// Lifecycle hooks + evolve-server (v1.69 convention)."
    )
    parts.append(
        "// Edit this file — the originals were standalone test programs."
    )
    parts.append("")

    if helpers:
        parts.append(
            "// ---- Top-level helpers (intent / pure fn from source files) ----"
        )
        parts.append("\n\n".join(helpers))
        parts.append("")

    parts.append("// ---- Lifecycle hooks ----")
    for hook in _HOOK_ORDER:
        block = hook_blocks.get(hook)
        if block is not None:
            parts.append(block)
            parts.append("")

    parts.append("// ---- evolve-server ----")
    # `evolve <name> { ... }` references an intent declaration. Lifecycle
    # agents don't usually have a single policy to evolve, so we emit
    # a minimal `heartbeat` intent and bind the evolve block to it. The
    # intent isn't called from any hook — it's just the parser's named
    # anchor point. Users editing the bundle can replace `heartbeat`
    # with a real policy intent later.
    parts.append(_HEARTBEAT_INTENT)
    parts.append("")
    parts.append(_render_evolve_block(
        intent_name="heartbeat",
        listen=listen,
        schedule_seconds=schedule_seconds,
        rollback_on=rollback_on,
    ))
    parts.append("")

    # Synthetic entry so the bundled module is also runnable as a
    # one-shot smoke test (`ail run arche.ail` invokes on_birth manually).
    parts.append("// ---- Synthetic entry (one-shot smoke test) ----")
    parts.append("entry main(input: Text) {")
    if "on_birth" in hook_blocks:
        parts.append("    return on_birth()")
    elif "on_tick" in hook_blocks:
        parts.append('    state = make_record([])')
        parts.append("    return on_tick(state)")
    else:
        # Fall back to whichever hook is present.
        first = next(h for h in _HOOK_ORDER if h in hook_blocks)
        if first == "on_genesis":
            parts.append("    return \"\" + to_text(on_genesis(make_record([])))")
        elif first in ("before_tick", "after_tick"):
            parts.append("    state = make_record([])")
            parts.append(f"    return {first}(state)")
        elif first == "on_dying":
            parts.append("    return on_dying(\"smoke\", [])")
        elif first == "on_death":
            parts.append("    return \"\" + to_text(on_death(make_record([])))")
        else:
            parts.append("    return \"bundled — no smoke entry\"")
    parts.append("}")

    src = "\n".join(parts) + "\n"
    output.write_text(src, encoding="utf-8")
    return BundleResult(
        source=src, used_files=used, skipped_files=skipped,
        output_path=output,
    )


_HEARTBEAT_INTENT = (
    'intent heartbeat() -> Text {\n'
    '    goal: "Return \'alive\' to confirm the agent is responding. '
    'Replace with a real evolved policy when the agent has one."\n'
    '}'
)


def _render_evolve_block(*, intent_name: str, listen: int,
                          schedule_seconds: int,
                          rollback_on: str) -> str:
    return (
        f"evolve {intent_name} {{\n"
        "    when request_received(req) {\n"
        "        // Default health check — replace with real routes if\n"
        "        // your service exposes HTTP. The lifecycle hooks above\n"
        "        // do the actual recurring work via the schedule.\n"
        "        perform http.respond(200, \"text/plain\", \"alive\")\n"
        "    }\n"
        f"    rollback_on: {rollback_on}\n"
        f"    schedule: every({schedule_seconds})\n"
        f"    listen: {listen}\n"
        "    history: keep_last 100\n"
        "}"
    )


def detect_lifecycle_files(project_root: Path) -> list[Path]:
    """Scan a project directory for standalone lifecycle .ail files.

    Returns the subset that look bundle-able: `<hook>.ail` with an
    `entry main` declaration. Used by the chat UI to surface the
    [🔧 합치기] CTA only when there's something to bundle.
    """
    found: list[Path] = []
    try:
        for p in sorted(project_root.iterdir()):
            if not p.is_file() or p.suffix != ".ail":
                continue
            if hook_name_from_path(p) is None:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            if re.search(r"\bentry\s+main\s*\(", text):
                found.append(p)
    except OSError:
        pass
    return found
