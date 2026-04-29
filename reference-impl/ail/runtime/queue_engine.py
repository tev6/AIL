"""Append-only message queue for agents.

Telos + Arche 2026-04-29 rebuild — sibling to scheduler self-throttle
and evolve rollback_on. Same Physis rule ("같은 실수를 반복하지 마라")
applied at message-processing layer: same message failing N times in
a row → dead-letter (auto-removed from active rotation, surfaced for
inspection).

Why a queue (Arche 2026-04-29 letter):
  Stoa is a letter store, not a queue. Stoa tells you a letter exists
  but doesn't track who took it, doesn't guarantee order, doesn't
  confirm processing. Agents need their own queue with explicit state
  transitions: pending → working → done | retry → ... → dead_letter.

Why append-only (Arche 2026-04-28 letter):
  *"deletion is movement. modification is addition. history only moves
  forward."* The queue file is a JSONL log of state transitions; the
  current state is derived by replay. Same shape as Stoa's
  message_log + Mneme's testament history. Crash-safe (no partial
  rewrites), audit-trail-by-construction.

Storage path:
  Pointed at by `AIL_QUEUE_FILE` env var (set by the agentic server to
  `<project>/.ail/queue.jsonl`). Outside an agentic project the var
  is unset and every queue effect returns an explanatory Result-error.

Record shapes on the wire:
  {"action": "push",  "id": "msg_001", "msg": {...}, "ts": float}
  {"action": "take",  "id": "msg_001",                "ts": float}
  {"action": "done",  "id": "msg_001",                "ts": float}
  {"action": "retry", "id": "msg_001",
                       "reason": "...", "count": 1,   "ts": float}
  {"action": "dead_letter",
                       "id": "msg_001",
                       "reason": "max retries (5)",   "ts": float}

dead_letter is auto-emitted by `retry` when the retry count reaches
DEAD_LETTER_AT. After dead_letter, the message is invisible to
`take` — only `inspect_dead_letters()` (future tooling) sees it.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


DEAD_LETTER_AT = 5  # Mirrors scheduler self-throttle threshold.


@dataclass
class QueueEntry:
    msg_id: str
    state: str               # "pending" | "working" | "done" | "dead_letter"
    msg: Any                 # original payload from push
    retry_count: int = 0
    last_reason: Optional[str] = None


def queue_file_path() -> Optional[Path]:
    """Resolve the queue file path from `AIL_QUEUE_FILE`.

    Returns None when unset — every effect handler converts that to a
    Result-error so the user gets an explanatory message instead of a
    crash.
    """
    raw = os.environ.get("AIL_QUEUE_FILE")
    if not raw:
        return None
    return Path(raw)


def replay(path: Path) -> dict[str, QueueEntry]:
    """Read the JSONL log and return current state for every msg_id.

    Records are processed strictly in append order. Unknown actions
    are skipped (forward-compat). The function is tolerant of malformed
    lines so a single bad record doesn't poison the entire queue.
    """
    entries: dict[str, QueueEntry] = {}
    if not path.is_file():
        return entries
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return entries
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(rec, dict):
            continue
        action = rec.get("action")
        msg_id = rec.get("id")
        if not isinstance(action, str) or not isinstance(msg_id, str):
            continue
        if action == "push":
            entries[msg_id] = QueueEntry(
                msg_id=msg_id,
                state="pending",
                msg=rec.get("msg"),
            )
        elif action == "take":
            e = entries.get(msg_id)
            if e is not None and e.state == "pending":
                e.state = "working"
        elif action == "done":
            e = entries.get(msg_id)
            if e is not None:
                e.state = "done"
        elif action == "retry":
            e = entries.get(msg_id)
            if e is not None:
                # Retry returns a working message back to pending and
                # bumps its counter. The ledger record carries the
                # post-bump count for human inspection; replay also
                # increments to reach the same number.
                e.state = "pending"
                e.retry_count += 1
                e.last_reason = rec.get("reason")
        elif action == "dead_letter":
            e = entries.get(msg_id)
            if e is not None:
                e.state = "dead_letter"
                e.last_reason = rec.get("reason")
    return entries


def _append(path: Path, record: dict) -> None:
    """Atomic append of one JSON record, with parent dir creation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    # `a` mode is atomic for small writes on POSIX (write(2) of a single
    # line < PIPE_BUF is atomic). Each record fits comfortably so
    # interleaved writers don't tear lines.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)


def _next_id(entries: dict[str, QueueEntry]) -> str:
    """Stable monotonic id: `msg_<n>` where n = len(entries) + 1."""
    n = len(entries) + 1
    while True:
        candidate = f"msg_{n:04d}"
        if candidate not in entries:
            return candidate
        n += 1  # collision (shouldn't happen but be safe)


def _ts() -> float:
    return time.time()


# ---------------------------------------------------------------- API

def push(path: Path, msg: Any) -> str:
    """Enqueue a new message. Returns the assigned msg_id."""
    entries = replay(path)
    msg_id = _next_id(entries)
    _append(path, {
        "action": "push",
        "id": msg_id,
        "msg": msg,
        "ts": _ts(),
    })
    return msg_id


def take(path: Path) -> Optional[dict]:
    """Atomically pick the oldest pending message and mark it working.

    Returns the message record (with `_id` field added) or None when
    the queue has no pending messages.
    """
    entries = replay(path)
    # Iteration order over `dict` is insertion order — i.e. push order.
    for msg_id, entry in entries.items():
        if entry.state == "pending":
            _append(path, {
                "action": "take",
                "id": msg_id,
                "ts": _ts(),
            })
            payload = _materialize(entry.msg)
            payload["_id"] = msg_id
            payload["_retry_count"] = entry.retry_count
            return payload
    return None


def done(path: Path, msg_id: str) -> bool:
    """Mark a working message complete. Returns True if accepted."""
    entries = replay(path)
    entry = entries.get(msg_id)
    if entry is None or entry.state != "working":
        return False
    _append(path, {
        "action": "done",
        "id": msg_id,
        "ts": _ts(),
    })
    return True


def retry(path: Path, msg_id: str, reason: str) -> str:
    """Send a working message back to pending with bumped retry count.

    Returns one of: "retried" (back to pending), "dead_letter" (count
    hit DEAD_LETTER_AT — auto-emitted), "not_found" (unknown id),
    "wrong_state" (id not in working state).
    """
    entries = replay(path)
    entry = entries.get(msg_id)
    if entry is None:
        return "not_found"
    if entry.state != "working":
        return "wrong_state"
    next_count = entry.retry_count + 1
    if next_count >= DEAD_LETTER_AT:
        _append(path, {
            "action": "dead_letter",
            "id": msg_id,
            "reason": (
                f"max retries ({DEAD_LETTER_AT}) reached: {reason}"
            ),
            "ts": _ts(),
        })
        return "dead_letter"
    _append(path, {
        "action": "retry",
        "id": msg_id,
        "reason": reason,
        "count": next_count,
        "ts": _ts(),
    })
    return "retried"


# ---------------------------------------------------------------- helpers

def _materialize(msg: Any) -> dict:
    """Coerce a queued payload into a dict so callers always get a
    record back. Lists `[[k, v], ...]` (AIL record literal shape) are
    folded to dicts; non-dict scalars get wrapped as `{value: ...}`.
    """
    if isinstance(msg, dict):
        return dict(msg)
    if isinstance(msg, list):
        try:
            return dict(msg)
        except (TypeError, ValueError):
            return {"value": msg}
    return {"value": msg}
