"""Command-line interface for AIL.

Usage:
    ail up [<dir>]                  # open the chat UI for a project
                                    # (auto-creates `.ail/` if missing)
    ail serve <dir>                 # run a project's programs as a service
    ail run <file.ail>              # execute a single .ail file
    ail bundle <on_*.ail>           # combine lifecycle files → evolve module
    ail doctor [<dir>]              # diagnose a project
    ail parse <file.ail>            # show AST (self-validation for agents)
    ail version

Telos + Arche 2026-04-29 rebuild — the CLI is now seven visible commands.
The chat UI is the primary entry; CLI exists to launch it (`ail up`),
run a one-off (`ail run`), or perform infra operations (serve / bundle /
doctor / parse). `ail init / ail ask / ail edit / ail chat / ail home`
were removed — `ail up <empty-dir>` auto-initializes, and natural-language
authoring lives entirely inside the chat UI.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from . import run, compile_source, AuthoringError, __version__
from .runtime import MockAdapter


def _find_free_port(preferred: int = 8080) -> int:
    """Return `preferred` if available, otherwise the next free port.
    Scans up to 64 ports above `preferred` to avoid wandering to weird
    high numbers; falls back to an OS-assigned port if that exhausts."""
    import socket
    for p in range(preferred, preferred + 64):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
            s.close()
            return p
        except OSError:
            s.close()
            continue
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _try_open_browser(url: str) -> None:
    """Best-effort open the URL in the user's default browser. Silent
    on failure — the URL is already printed to stdout."""
    try:
        import webbrowser
        webbrowser.open(url, new=1, autoraise=True)
    except Exception:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ail", description="AIL MVP interpreter")
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_run = sub.add_parser("run", help="Run an AIL program")
    p_run.add_argument("file", help="Path to .ail source file")
    p_run.add_argument("--input", default=None, help="Input to the entry's first parameter")
    p_run.add_argument("--trace", action="store_true", help="Print execution trace")
    p_run.add_argument("--trace-json", action="store_true", help="Print trace as JSON")
    p_run.add_argument("--mock", action="store_true",
                       help="Use mock adapter (no model calls). Equivalent to --adapter mock.")
    p_run.add_argument(
        "--adapter", default=None,
        choices=["ollama", "anthropic", "openai", "mock"],
        help="Force a specific model adapter. Overrides env-var auto-detection. "
             "Without this flag, the env order is: AIL_OLLAMA_MODEL → "
             "ANTHROPIC_API_KEY → AIL_OPENAI_COMPAT_MODEL/OPENAI_API_KEY. "
             "The chosen adapter + model is printed to stderr at startup so "
             "you always know which model is running.")
    p_run.add_argument("--raw", action="store_true",
                       help="Print only the return value on a single line "
                            "(no header, no confidence, no trace). "
                            "Matches the Go runtime's default output shape, "
                            "enabling shell-level conformance comparison.")

    p_parse = sub.add_parser("parse", help="Parse and print AST")
    p_parse.add_argument("file", help="Path to .ail source file")

    p_up = sub.add_parser("up",
        help="Open the chat UI for a project (auto-creates the directory's "
             "`.ail/` state on first run). Primary entry point — type natural "
             "language and the agent emits .ail files / runs them.")
    p_up.add_argument("path", nargs="?", default=".",
        help="Project directory (default: current directory)")
    p_up.add_argument("--port", type=int, default=None,
        help="Override the port from INTENT.md ## Deployment")
    p_up.add_argument("--no-serve", action="store_true",
        help="Author + run tests, then exit. Don't start the HTTP server.")
    p_up.add_argument("--no-watch", action="store_true",
        help="Skip the file-watch background loop. By default `ail up` "
             "polls INTENT.md and app.ail for edits and re-runs the "
             "declared tests on change without restarting the server.")
    p_up.add_argument("--retries", type=int, default=3,
        help="Max retries if the author emits invalid AIL (default 3)")
    p_up.add_argument("--auto-fix", type=int, default=0, metavar="N",
        help="If declared tests fail, hand the failures to the chat "
             "backend and retry up to N times. Costs LLM calls — "
             "default 0 (off).")
    p_up.add_argument("--log", choices=["friendly", "compact"],
        default="friendly",
        help="Output style. `friendly` (default) is for end users; "
             "`compact` is the original v1.9.0 dev-style one-liners "
             "useful for scripts and CI.")

    p_serve = sub.add_parser("serve",
        help="Run a project's programs WITHOUT the authoring chat. "
             "This is the 'independent execution' mode per "
             "PRINCIPLES.md §5 — the chat session can be closed; the "
             "server keeps schedule.every ticks firing and the "
             "view.html dashboard accessible at /run. Run in a "
             "separate terminal (or tmux) from `ail up`; both can "
             "coexist on different ports against the same project.")
    p_serve.add_argument("path", nargs="?", default=".",
        help="Project directory (default: current directory)")
    p_serve.add_argument("--port", type=int, default=8090,
        help="Port to serve on (default 8090, distinct from ail up's "
             "default 8080 so both can run side-by-side).")
    p_serve.add_argument("--host", default="127.0.0.1",
        help="Host to bind (default 127.0.0.1). Use 0.0.0.0 to expose "
             "on the LAN for field-testing.")

    p_bundle = sub.add_parser("bundle",
        help="Combine scattered lifecycle .ail files into one evolve-server. "
             "Humans naturally split work into small files (on_birth.ail, "
             "on_tick.ail, …) for verification, but v1.67/1.68 lifecycle "
             "hooks are recognized only inside one module with an evolve "
             "block. `ail bundle` rewrites the parts as fn-convention "
             "hooks + a default Physis evolve block, so the result is "
             "deploy-eligible without rewriting any logic.")
    p_bundle.add_argument("files", nargs="+",
        help="Source .ail files. Names matter: `on_birth.ail` becomes "
             "`fn on_birth()`, `on_tick.ail` → `fn on_tick(state)`, etc. "
             "Files whose stem isn't a known hook are skipped.")
    p_bundle.add_argument("--output", "-o", default=None,
        help="Output file (default: <project>/<project>.ail next to the "
             "first input).")
    p_bundle.add_argument("--listen", type=int, default=8090,
        help="Listen port baked into the evolve block (default 8090).")
    p_bundle.add_argument("--every", type=int, default=60,
        help="schedule.every() seconds in the evolve block (default 60).")
    p_bundle.add_argument("--rollback-on", default=None,
        help="Custom rollback_on expression. Default: "
             "'error_rate > 0.5 or consecutive_failures > 5' — the Physis "
             "default. Arche directive 2026-04-29: never empty.")

    p_doctor = sub.add_parser("doctor",
        help="Diagnose an AIL project — flags scaffold leftovers, "
             "missing evolve blocks, orphan schedules, parse errors, "
             "and other shapes that block deploy. 5-second version of "
             "what would otherwise be a 30-min debugging session.")
    p_doctor.add_argument("path", nargs="?", default=".",
        help="Project directory (default: current directory).")
    p_doctor.add_argument("--json", action="store_true",
        help="Emit machine-readable JSON instead of formatted text.")

    sub.add_parser("version", help="Print version")

    p_stoa = sub.add_parser("stoa", help="Stoa identity tools")
    stoa_sub = p_stoa.add_subparsers(dest="stoa_cmd")
    p_keygen = stoa_sub.add_parser(
        "keygen",
        help="Generate ed25519 key pair and register public key on Stoa (RFC-001 §6).",
    )
    p_keygen.add_argument(
        "--identity", "-i",
        default=None,
        help="Agent identity name (default: git config ail.identity).",
    )
    p_keygen.add_argument(
        "--stoa-url",
        default=None,
        help="Stoa base URL (default: $STOA_BASE_URL or https://ail-stoa.up.railway.app).",
    )
    p_keygen.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and save keys but skip Stoa registration.",
    )

    args = parser.parse_args(argv)

    if args.cmd is None:
        # Telos + Arche 2026-04-29 — bare `ail` no longer launches a
        # file-tree home (was `ail home`). Print a tiny pointer to the
        # primary command so a non-developer who mistyped or expected
        # auto-launch sees the path forward in one line.
        print(
            "AIL — chat-based agent authoring.\n"
            "\n"
            "  ail up [<dir>]      # open chat UI (auto-init if empty)\n"
            "  ail run <file.ail>  # run a single file\n"
            "  ail doctor [<dir>]  # diagnose a project\n"
            "  ail --help          # full command list\n"
        )
        return 0

    if args.cmd == "version":
        print(f"ail {__version__}")
        return 0

    if args.cmd == "stoa":
        return _handle_stoa(args)


    if args.cmd == "up":
        from .agentic import Project, bring_up
        try:
            proj = Project.at(args.path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return bring_up(
            proj,
            max_retries=args.retries,
            serve=not args.no_serve,
            port_override=args.port,
            watch=not args.no_watch,
            auto_fix_attempts=args.auto_fix,
            log_style=args.log,
        )

    if args.cmd == "serve":
        from .agentic import Project
        from .agentic.server import serve_project
        try:
            proj = Project.at(args.path)
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        print(f"Serving {proj.root.name} on http://{args.host}:{args.port}/run")
        print(f"  (chat UI disabled — independent execution mode)")
        print(f"  (Ctrl+C to stop)\n")
        return serve_project(
            proj, port=args.port, host=args.host, watch=False,
            serve_only=True,
        )

    if args.cmd == "doctor":
        from .doctor import diagnose, render_report
        root = Path(args.path).expanduser().resolve()
        if not root.is_dir():
            print(f"not a directory: {root}", file=sys.stderr)
            return 1
        report = diagnose(root)
        if args.json:
            import json as _json
            payload = {
                "project_root": str(report.project_root),
                "findings": [
                    {
                        "severity": f.severity,
                        "code": f.code,
                        "message": f.message,
                        "hint": f.hint,
                    }
                    for f in report.findings
                ],
            }
            print(_json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(render_report(report), end="")
        return 1 if report.errors else 0

    if args.cmd == "bundle":
        from .bundle import bundle, DEFAULT_ROLLBACK_ON
        files = [Path(f).expanduser() for f in args.files]
        missing = [str(f) for f in files if not f.is_file()]
        if missing:
            print(f"missing files: {', '.join(missing)}", file=sys.stderr)
            return 1
        if args.output:
            output = Path(args.output).expanduser()
        else:
            # Default: <first-input-parent>/<dirname>.ail
            parent = files[0].parent.resolve()
            output = parent / f"{parent.name}.ail"
        rb = args.rollback_on or DEFAULT_ROLLBACK_ON
        result = bundle(
            files,
            output=output,
            listen=args.listen,
            schedule_seconds=args.every,
            rollback_on=rb,
        )
        if not result.used_files:
            print(
                "no lifecycle files matched (expected stems like "
                "on_genesis / on_birth / on_tick / before_tick / "
                "after_tick / on_dying / on_death).",
                file=sys.stderr,
            )
            return 2
        print(f"✓ bundled {len(result.used_files)} file(s) → {output}")
        for u in result.used_files:
            print(f"    + {u}")
        if result.skipped_files:
            print("  skipped (not a recognized hook stem):")
            for s in result.skipped_files:
                print(f"    - {s}")
        print(
            f"\nNext: edit {output.name} (rollback_on / schedule / listen "
            f"are defaulted), then `ail up {output.parent}` and click "
            f"the inline [🚀 지금 배포하기] card."
        )
        return 0

    if args.cmd == "parse":
        source = Path(args.file).read_text(encoding="utf-8")
        program = compile_source(source)
        print(f"Program with {len(program.declarations)} declarations:")
        for d in program.declarations:
            # Different declaration types have different name fields
            label = _declaration_label(d)
            print(f"  {type(d).__name__}: {label}")
        return 0

    if args.cmd == "run":
        # Adapter selection precedence (Arche v1.60.9 review action item):
        # explicit --mock → mock; explicit --adapter NAME → that adapter;
        # otherwise env-var auto-detect via _default_adapter().
        # Whichever wins, print the choice to stderr so the user is never
        # left wondering which model is running.
        from . import adapter_from_name, describe_adapter, _resolve_adapter_name_from_env
        if args.mock:
            adapter = MockAdapter()
        elif getattr(args, "adapter", None):
            adapter = adapter_from_name(args.adapter)
        else:
            adapter = None  # run() will call _default_adapter()
        chosen = adapter
        if chosen is None:
            # Replicate the env resolution so we can print the same choice
            # the runtime is about to make.
            from . import _default_adapter
            chosen = _default_adapter()
            adapter = chosen
        print(f"[ail: using {describe_adapter(chosen)} adapter]",
              file=sys.stderr)
        try:
            result, trace = run(args.file, input=args.input, adapter=adapter)
        except Exception as e:
            print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
            return 1

        if args.raw:
            # Value only — matches go-impl's default output shape so
            # the two runtimes can be compared byte-for-byte. Python
            # floats print as `5040.0`; Go prints whole-valued numbers
            # without the trailing `.0`. Normalize Python output to
            # match so conformance cases agree across runtimes.
            print(_format_value_raw(result.value))
            return 0

        print("=" * 60)
        print("RESULT")
        print("=" * 60)
        print(f"value: {result.value}")
        print(f"confidence: {result.confidence:.3f}")

        if args.trace_json:
            print()
            print("=" * 60)
            print("TRACE (JSON)")
            print("=" * 60)
            print(trace.to_json())
        elif args.trace:
            print()
            print("=" * 60)
            print("TRACE")
            print("=" * 60)
            print(trace.pretty())

        return 0

    return 0


def _format_value_raw(value) -> str:
    """Render a ConfidentValue.value for `ail run --raw` in a shape
    that matches go-impl's default printer.

    - Floats that happen to be whole numbers (5040.0) drop the `.0`
      and print as integers. This reconciles the two runtimes on the
      common case without changing runtime semantics — Number in AIL
      is still float-backed in Python.
    - Everything else falls through to the default str() so lists,
      dicts, booleans, and non-integer floats are unchanged.
    """
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _declaration_label(d) -> str:
    """Return a human-friendly label for each declaration type."""
    # Each declaration kind has its own primary-name field
    if hasattr(d, "name"):
        return d.name
    if hasattr(d, "intent_name"):   # EvolveDecl
        return f"for {d.intent_name}"
    if hasattr(d, "source"):        # ImportDecl
        sym = getattr(d, "symbol", "")
        return f"{sym} from {d.source!r}" if sym else d.source
    return "?"


def _handle_stoa(args) -> int:
    if args.stoa_cmd == "keygen":
        from .stoa import keygen, resolve_identity

        identity = args.identity or resolve_identity()
        if not identity:
            print(
                "error: identity not found. Pass --identity <name> or run:\n"
                "  git config --worktree ail.identity <name>",
                file=sys.stderr,
            )
            return 1

        stoa_url = (
            args.stoa_url
            or os.environ.get("STOA_BASE_URL", "https://ail-stoa.up.railway.app")
        )

        print(f"Generating ed25519 key pair for '{identity}' …")
        result = keygen(identity, stoa_url, dry_run=args.dry_run)

        print(f"  private key  {result['sk_path']}  (chmod 600)")
        print(f"  public key   {result['pk_path']}")
        print(f"  pk_hex       {result['pk_hex'][:16]}…")
        if args.dry_run:
            print("  (dry-run — Stoa registration skipped)")
        elif result["registered"]:
            print(f"  registered   ✓ {stoa_url}")
        else:
            print(
                f"  registered   ✗ (Stoa POST failed — run manually)\n"
                f"    curl -X POST {stoa_url}/api/v1/agents \\\n"
                f"      -H 'Content-Type: application/json' \\\n"
                f"      -d '{{\"name\":\"{identity}\","
                f"\"address\":\"{stoa_url}/inbox/{identity}\","
                f"\"public_key\":\"{result['pk_hex']}\"}}'",
            )
        return 0

    print("usage: ail stoa <subcommand>\n\nsubcommands:\n  keygen   generate + register ed25519 key")
    return 1


if __name__ == "__main__":
    sys.exit(main())
