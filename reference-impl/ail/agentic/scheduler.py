"""Background scheduler for agentic projects.

An AIL program can call `perform schedule.every(seconds)` from inside
`entry main`. That effect only *registers* a cadence — it writes
`{"seconds": N}` into the schedule file pointed at by AIL_SCHEDULE_FILE.
The loop that actually re-invokes the entry on that cadence lives here.

Design choices:

- One thread per project. Polls the schedule file every ~0.5s for
  changes. When the seconds value changes, the recurring invocation
  cadence updates on the next tick — no restart needed.
- Each tick re-invokes `entry main("")` in-process (same interpreter
  the server uses) and records the outcome to the ledger with
  `event: "schedule_tick"`. Success or failure of the tick doesn't
  stop the schedule by itself.
- **Self-throttle (Physis at the scheduler layer, hyun06000 + Arche
  2026-04-29).** When the same error signature repeats `THROTTLE_AFTER_N`
  times in a row, the scheduler writes `paused: true` into the schedule
  file and emits a `schedule_throttled` ledger event. The chat UI
  surfaces a yellow card with [다시 켜기]; clearing `paused` resets
  the counters and resumes ticks. *"같은 실수를 반복하지 마라"*가
  자가수리 ■ 중단 / evolve rollback_on과 같은 원리로 스케줄러에도
  적용되는 것.
- Entry can write results to state via `perform state.write(...)`,
  so GET / (which runs entry fresh each time) sees the latest output.
- Stop() is cooperative via a threading.Event. The server calls it
  on shutdown before closing the HTTPServer.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Optional


class Scheduler:
    """Polls a schedule file and drives recurring entry invocations.

    Use:
        sched = Scheduler(project, schedule_file, invoke_fn)
        sched.start()
        ... later ...
        sched.stop()

    `invoke_fn()` is a zero-arg callable that re-runs the project's
    entry. It can either return None (legacy — tracking disabled) or
    a `(ok: bool, signature: str)` tuple. When it returns the tuple,
    the scheduler counts consecutive failures with the same signature
    and auto-pauses after THROTTLE_AFTER_N hits.
    """

    # Poll interval for the schedule-file watcher itself. Separate
    # from the user-declared cadence (which can be minutes or days).
    POLL_SECONDS = 0.5

    # Auto-pause after this many consecutive failures with the same
    # error signature. Mirrors the proposed evolve rollback_on default
    # (`consecutive_failures > 5`) so the language speaks one rule at
    # both layers.
    THROTTLE_AFTER_N = 5

    def __init__(
        self,
        *,
        schedule_file: Path,
        invoke: "callable",
        logger=None,
        on_throttle: "callable | None" = None,
    ):
        self._schedule_file = Path(schedule_file)
        self._invoke = invoke
        self._logger = logger
        self._on_throttle = on_throttle
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # State of the currently active schedule. _seconds=None means
        # the file hasn't appeared yet or is invalid.
        self._seconds: Optional[float] = None
        self._next_tick: float = 0.0
        self._paused: bool = False
        self._consecutive_failures: int = 0
        self._last_failure_signature: Optional[str] = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="ail-scheduler", daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._check_schedule()
            if (
                not self._paused
                and self._seconds is not None
                and time.time() >= self._next_tick
            ):
                self._tick()
                self._next_tick = time.time() + self._seconds
            # Cooperative sleep — wakes early on stop().
            self._stop.wait(self.POLL_SECONDS)

    def _check_schedule(self) -> None:
        """Re-read the schedule file; update active cadence if changed."""
        try:
            if not self._schedule_file.is_file():
                return
            payload = json.loads(
                self._schedule_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        if not isinstance(payload, dict):
            return

        # Pause flag — user-clearable via /authoring-schedule/resume.
        # Transition out of paused → reset counters so the next failure
        # window starts fresh (otherwise an old signature would re-trip
        # immediately).
        paused = bool(payload.get("paused"))
        if paused != self._paused:
            self._paused = paused
            if not paused:
                self._consecutive_failures = 0
                self._last_failure_signature = None

        raw = payload.get("seconds")
        try:
            seconds = float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return
        if seconds is None or seconds <= 0:
            return

        if seconds != self._seconds:
            self._seconds = seconds
            # First tick fires one cadence-interval from now, not
            # immediately — the request that registered the schedule
            # already ran the work once.
            self._next_tick = time.time() + seconds
            if self._logger is not None:
                try:
                    self._logger.schedule_armed(seconds)
                except AttributeError:
                    pass

    def _tick(self) -> None:
        try:
            outcome = self._invoke()
        except Exception as e:
            outcome = (False, f"{type(e).__name__}: {e}")

        if outcome is None:
            # Legacy invoke that returns nothing — disable throttle
            # bookkeeping for this caller. Behaviour matches pre-1.69.
            return

        try:
            ok, signature = outcome
        except (TypeError, ValueError):
            return

        if ok:
            self._consecutive_failures = 0
            self._last_failure_signature = None
            return

        sig = (signature or "")[:200]
        if sig and sig == self._last_failure_signature:
            self._consecutive_failures += 1
        else:
            self._consecutive_failures = 1
            self._last_failure_signature = sig

        if self._consecutive_failures >= self.THROTTLE_AFTER_N:
            self._auto_pause(sig)

    def _auto_pause(self, signature: str) -> None:
        """Persist `paused: true` to the schedule file and notify."""
        try:
            payload_text = self._schedule_file.read_text(encoding="utf-8")
            payload = json.loads(payload_text)
        except (OSError, json.JSONDecodeError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        payload["paused"] = True
        payload["paused_reason"] = signature
        payload["paused_consecutive_failures"] = self._consecutive_failures
        payload["paused_at"] = time.time()
        try:
            self._schedule_file.write_text(
                json.dumps(payload), encoding="utf-8",
            )
        except OSError:
            pass
        # _check_schedule will read paused=True on next loop pass; set
        # locally too so a tick already in flight doesn't queue another.
        self._paused = True
        if self._on_throttle is not None:
            try:
                self._on_throttle(signature, self._consecutive_failures)
            except Exception:
                pass
