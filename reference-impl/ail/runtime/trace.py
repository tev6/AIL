"""Trace ledger for the MVP.

Real AIRT writes to an append-only store. The MVP keeps traces in memory
and can dump them as structured JSON. Every intent invocation, context
resolution, constraint check, and model call appears as an entry.

Thread-safety: `record`, `enter`, and `exit` are protected by an internal
lock so that parallel execution (Phase 4) doesn't corrupt the entry list
or produce interleaved `_depth` counters that end up negative. Trace
order across parallel branches is not guaranteed to reflect wall-clock
start order — it reflects the order in which record() was called.

Bounded by default (cycle 13 v1.75.1 hotfix — Stoa OOM RCA traced
trace.py:45 as the leak). `entries` is a `collections.deque` with a
default cap of 10,000; old entries are evicted as new ones arrive. Set
`AIL_TRACE_MAX_ENTRIES` (positive int) to change the cap, or
`AIL_TRACE_UNBOUNDED=1` to disable it entirely (the old behavior — keep
for short-lived test runs that introspect the full trace).
"""
from __future__ import annotations
import collections
import json
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class TraceEntry:
    timestamp: float
    kind: str                    # intent_call | model_call | constraint_check | perform | branch | context_push | ...
    payload: dict[str, Any]
    depth: int = 0


class Trace:
    def __init__(self):
        self._lock = threading.Lock()
        self._depth = 0
        unbounded = os.environ.get("AIL_TRACE_UNBOUNDED") == "1"
        if unbounded:
            # Old behavior. An evolve server in this mode grows trace
            # memory linearly forever — only use it for short test runs
            # that need every entry available for inspection.
            self.entries: collections.deque[TraceEntry] = collections.deque()
        else:
            try:
                max_entries = int(os.environ.get(
                    "AIL_TRACE_MAX_ENTRIES", "10000"))
            except ValueError:
                max_entries = 10000
            if max_entries < 1:
                max_entries = 10000
            self.entries = collections.deque(maxlen=max_entries)

    def enter(self) -> None:
        with self._lock:
            self._depth += 1

    def exit(self) -> None:
        with self._lock:
            self._depth = max(0, self._depth - 1)

    def record(self, kind: str, **payload: Any) -> None:
        with self._lock:
            self.entries.append(TraceEntry(
                timestamp=time.time(),
                kind=kind,
                payload=payload,
                depth=self._depth,
            ))

    def to_list(self) -> list[dict[str, Any]]:
        return [
            {"ts": e.timestamp, "depth": e.depth, "kind": e.kind, **e.payload}
            for e in self.entries
        ]

    def to_json(self, indent: int = 2) -> str:
        # fall back to str for non-serializable values
        return json.dumps(self.to_list(), indent=indent, default=str, ensure_ascii=False)

    def pretty(self) -> str:
        lines: list[str] = []
        for e in self.entries:
            prefix = "  " * e.depth
            # Concise one-line per entry
            payload_str = ", ".join(f"{k}={_fmt(v)}" for k, v in e.payload.items())
            lines.append(f"{prefix}[{e.kind}] {payload_str}")
        return "\n".join(lines)


def _fmt(v: Any, maxlen: int = 80) -> str:
    s = str(v)
    if len(s) > maxlen:
        return s[: maxlen - 3] + "..."
    return s
