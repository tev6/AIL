"""Tekton outbox dispatcher — transport layer for the autonomous pilot.

Polls `AIL_STATE_DIR/tekton.outbox.<ts>.json`, hands each letter to
community-tools/stoa-cli (signed envelope via the AIL#6 Phase 2 sidecar),
then renames the file to `tekton.outbox_done.<ts>.json` so the same letter
never goes out twice.

Why a Python sidecar (and not pure AIL):
  - AIL has no `process.spawn` / `shell.exec` effect, so the charter
    cannot invoke stoa-cli directly.
  - Re-implementing canonical_letter inside AIL would cross the
    Rule 16 D2 boundary (Stoa owns canonical envelope serialization).
  - This split also isolates fail modes: charter failures don't lose
    ledger entries, dispatcher failures don't lose decisions.

Run:
    AIL_STATE_DIR=agents/tekton/.state \\
        python3 agents/tekton/outbox_dispatch.py --loop

One-shot drain (no loop):
    python3 agents/tekton/outbox_dispatch.py --once
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
STOA_CLI = REPO_ROOT / "community-tools" / "stoa-cli" / "stoa_cli.py"
KEYS_DIR = Path(os.environ.get("STOA_HOME", str(Path.home() / ".ail" / "keys")))
SENDER = os.environ.get("STOA_NAME", "tekton")


def state_dir() -> Path:
    raw = os.environ.get("AIL_STATE_DIR")
    if not raw:
        sys.exit("AIL_STATE_DIR must be set (e.g. agents/tekton/.state)")
    p = Path(raw)
    p.mkdir(parents=True, exist_ok=True)
    return p


def pending_outbox(d: Path) -> list[Path]:
    return sorted(d.glob("tekton.outbox.*.json"))


def send_one(letter_path: Path) -> bool:
    """Send a single outbox letter. Returns True on success."""
    payload = json.loads(letter_path.read_text(encoding="utf-8"))
    recipients = payload.get("to") or []
    subject = payload.get("subject") or "(no subject)"
    content_body = payload.get("content") or ""
    ledger_id = payload.get("ledger_id") or "?"

    # Stoa convention: subject on first line, body after `---` separator.
    composed = (
        f"{subject}\n"
        f"---\n\n"
        f"{content_body}\n\n"
        f"(autonomous tekton — ledger {ledger_id})"
    )

    if not recipients:
        print(f"skip {letter_path.name}: empty recipients", file=sys.stderr)
        return False

    # stoa-cli `send` takes a single recipient + content. Fan out one
    # POST per recipient; signature is computed per envelope.
    ok_count = 0
    for r in recipients:
        cmd = [
            sys.executable, str(STOA_CLI), "send", r, composed,
        ]
        env = os.environ | {
            "STOA_HOME": str(KEYS_DIR),
            "STOA_NAME": SENDER,
        }
        try:
            res = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            print(f"timeout sending to {r}: {letter_path.name}", file=sys.stderr)
            continue
        if res.returncode != 0:
            print(f"send to {r} failed (exit {res.returncode}): {res.stderr.strip()}", file=sys.stderr)
            continue
        # stoa-cli prints the envelope JSON on success; capture the id.
        try:
            env_out = json.loads(res.stdout)
            mid = env_out.get("envelope", {}).get("id") or "?"
        except json.JSONDecodeError:
            mid = "?"
        print(f"sent {letter_path.name} → {r} as {mid}")
        ok_count += 1
    return ok_count == len(recipients)


def drain_once(d: Path) -> int:
    n = 0
    for path in pending_outbox(d):
        if send_one(path):
            # rename to *_done so list_keys / glob no longer matches.
            done = path.with_name(path.name.replace("tekton.outbox.", "tekton.outbox_done.", 1))
            path.rename(done)
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--once", action="store_true", help="drain pending outbox and exit")
    grp.add_argument("--loop", action="store_true", help="poll forever")
    parser.add_argument("--interval", type=float, default=60.0, help="loop poll interval (seconds)")
    args = parser.parse_args(argv)

    d = state_dir()
    if not STOA_CLI.exists():
        sys.exit(f"stoa-cli not found at {STOA_CLI}")

    if args.once:
        n = drain_once(d)
        print(f"drained {n} letter(s)")
        return 0

    print(f"tekton outbox dispatcher: watching {d} every {args.interval}s")
    while True:
        try:
            drain_once(d)
        except Exception as e:
            print(f"drain error: {type(e).__name__}: {e}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
