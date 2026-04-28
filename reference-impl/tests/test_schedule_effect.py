"""Tests for `perform schedule.every(N)` — the registration effect
and the background Scheduler loop that drives re-invocation."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from ail import run as ail_run
from ail.agentic.scheduler import Scheduler


# ---------- effect: schedule file write ----------


SCHEDULE_REGISTERING_AIL = """\
entry main(input: Text) {
    r = perform schedule.every(5)
    if is_ok(r) {
        return "armed"
    }
    return unwrap_error(r)
}
"""


def test_schedule_effect_writes_schedule_file(tmp_path, monkeypatch):
    # Point the effect at a throwaway schedule file and invoke entry.
    sched_path = tmp_path / "schedule.json"
    monkeypatch.setenv("AIL_SCHEDULE_FILE", str(sched_path))
    src = tmp_path / "app.ail"
    src.write_text(SCHEDULE_REGISTERING_AIL, encoding="utf-8")

    result, _trace = ail_run(str(src), input="")
    assert result.value == "armed"
    assert sched_path.is_file()
    payload = json.loads(sched_path.read_text(encoding="utf-8"))
    assert payload == {"seconds": 5.0}


def test_schedule_effect_without_env_returns_error(tmp_path, monkeypatch):
    # Outside `ail up` the effect has nowhere to write; must error cleanly.
    monkeypatch.delenv("AIL_SCHEDULE_FILE", raising=False)
    src = tmp_path / "app.ail"
    src.write_text(SCHEDULE_REGISTERING_AIL, encoding="utf-8")
    result, _trace = ail_run(str(src), input="")
    assert "no scheduler running" in result.value.lower()


def test_schedule_effect_rejects_non_positive(tmp_path, monkeypatch):
    monkeypatch.setenv("AIL_SCHEDULE_FILE", str(tmp_path / "s.json"))
    src = tmp_path / "app.ail"
    src.write_text("""\
entry main(input: Text) {
    r = perform schedule.every(0)
    return unwrap_error(r)
}
""", encoding="utf-8")
    result, _trace = ail_run(str(src), input="")
    assert "> 0" in result.value


def test_schedule_effect_rejects_over_day(tmp_path, monkeypatch):
    monkeypatch.setenv("AIL_SCHEDULE_FILE", str(tmp_path / "s.json"))
    src = tmp_path / "app.ail"
    src.write_text("""\
entry main(input: Text) {
    r = perform schedule.every(100000)
    return unwrap_error(r)
}
""", encoding="utf-8")
    result, _trace = ail_run(str(src), input="")
    assert "86400" in result.value


def test_schedule_effect_latest_call_wins(tmp_path, monkeypatch):
    sched_path = tmp_path / "schedule.json"
    monkeypatch.setenv("AIL_SCHEDULE_FILE", str(sched_path))
    src = tmp_path / "app.ail"
    src.write_text("""\
entry main(input: Text) {
    perform schedule.every(10)
    perform schedule.every(30)
    return "ok"
}
""", encoding="utf-8")
    ail_run(str(src), input="")
    payload = json.loads(sched_path.read_text(encoding="utf-8"))
    assert payload == {"seconds": 30.0}


# ---------- Scheduler loop ----------


class _FastScheduler(Scheduler):
    POLL_SECONDS = 0.02


def test_scheduler_does_not_fire_when_no_file(tmp_path):
    calls = []
    sched = _FastScheduler(
        schedule_file=tmp_path / "missing.json",
        invoke=lambda: calls.append(time.time()),
    )
    sched.start()
    time.sleep(0.2)
    sched.stop()
    assert calls == []


def test_scheduler_fires_at_declared_cadence(tmp_path):
    sched_path = tmp_path / "s.json"
    sched_path.write_text(json.dumps({"seconds": 0.1}), encoding="utf-8")
    calls = []
    sched = _FastScheduler(
        schedule_file=sched_path,
        invoke=lambda: calls.append(time.time()),
    )
    sched.start()
    # First tick fires one interval after the file is read, so allow
    # ~0.5s to see at least 2 ticks at 0.1s cadence.
    time.sleep(0.5)
    sched.stop()
    assert len(calls) >= 2, f"expected >=2 ticks, got {len(calls)}"


def test_scheduler_stops_cleanly(tmp_path):
    sched_path = tmp_path / "s.json"
    sched_path.write_text(json.dumps({"seconds": 0.05}), encoding="utf-8")
    calls = []
    sched = _FastScheduler(
        schedule_file=sched_path,
        invoke=lambda: calls.append(None),
    )
    sched.start()
    time.sleep(0.2)
    sched.stop(timeout=1.0)
    before = len(calls)
    time.sleep(0.3)
    # After stop(), no further ticks should fire.
    assert len(calls) == before


def test_scheduler_swallows_invoke_exceptions(tmp_path):
    sched_path = tmp_path / "s.json"
    sched_path.write_text(json.dumps({"seconds": 0.05}), encoding="utf-8")
    call_count = {"n": 0}

    def _boom():
        call_count["n"] += 1
        raise RuntimeError("upstream down")

    sched = _FastScheduler(schedule_file=sched_path, invoke=_boom)
    sched.start()
    time.sleep(0.3)
    sched.stop()
    # Multiple ticks fired despite each one raising.
    assert call_count["n"] >= 2


def test_scheduler_ignores_malformed_schedule_file(tmp_path):
    sched_path = tmp_path / "s.json"
    sched_path.write_text("not-json", encoding="utf-8")
    calls = []
    sched = _FastScheduler(
        schedule_file=sched_path,
        invoke=lambda: calls.append(None),
    )
    sched.start()
    time.sleep(0.2)
    sched.stop()
    assert calls == []


def test_scheduler_picks_up_cadence_change(tmp_path):
    sched_path = tmp_path / "s.json"
    sched_path.write_text(json.dumps({"seconds": 1.0}), encoding="utf-8")
    calls = []
    sched = _FastScheduler(
        schedule_file=sched_path,
        invoke=lambda: calls.append(None),
    )
    sched.start()
    time.sleep(0.1)
    # Drop cadence to a short interval — next poll should reset timing.
    sched_path.write_text(json.dumps({"seconds": 0.05}), encoding="utf-8")
    time.sleep(0.4)
    sched.stop()
    assert len(calls) >= 2


# ---------- Self-throttle (Telos 2026-04-29) ----------


class _ThrottleScheduler(Scheduler):
    POLL_SECONDS = 0.02
    THROTTLE_AFTER_N = 3  # Lower bar for fast tests


def test_scheduler_auto_pauses_after_consecutive_failures(tmp_path):
    """Same-signature failures repeated N times → schedule.json gets
    paused: true + the throttle callback fires."""
    sched_path = tmp_path / "s.json"
    sched_path.write_text(json.dumps({"seconds": 0.05}), encoding="utf-8")
    throttle_events = []
    sched = _ThrottleScheduler(
        schedule_file=sched_path,
        invoke=lambda: (False, "Input cannot be empty"),
        on_throttle=lambda sig, n: throttle_events.append((sig, n)),
    )
    sched.start()
    time.sleep(0.5)
    sched.stop()

    # Throttle should have fired at least once after N=3 failures.
    assert throttle_events, (
        "expected throttle callback after consecutive failures")
    sig, count = throttle_events[0]
    assert "Input cannot be empty" in sig
    assert count >= 3

    payload = json.loads(sched_path.read_text(encoding="utf-8"))
    assert payload.get("paused") is True
    assert payload.get("paused_consecutive_failures") >= 3
    assert "Input cannot be empty" in (payload.get("paused_reason") or "")


def test_scheduler_does_not_pause_when_signature_changes(tmp_path):
    """Different error signatures should NOT count as consecutive."""
    sched_path = tmp_path / "s.json"
    sched_path.write_text(json.dumps({"seconds": 0.05}), encoding="utf-8")
    counter = {"i": 0}

    def invoke():
        counter["i"] += 1
        return (False, f"err-{counter['i']}")  # always-different sig

    throttle_events = []
    sched = _ThrottleScheduler(
        schedule_file=sched_path,
        invoke=invoke,
        on_throttle=lambda sig, n: throttle_events.append((sig, n)),
    )
    sched.start()
    time.sleep(0.5)
    sched.stop()
    assert throttle_events == [], (
        "different signatures must not throttle")


def test_scheduler_resume_clears_paused_and_resets_counter(tmp_path):
    """Externally clearing `paused` (= the /resume endpoint) should
    re-arm the scheduler with fresh failure counters."""
    sched_path = tmp_path / "s.json"
    sched_path.write_text(json.dumps({"seconds": 0.05}), encoding="utf-8")
    invoke_calls = []
    invoke_outcome = {"ok": False, "sig": "boom"}

    def invoke():
        invoke_calls.append(time.time())
        return (invoke_outcome["ok"], invoke_outcome["sig"])

    sched = _ThrottleScheduler(
        schedule_file=sched_path,
        invoke=invoke,
    )
    sched.start()
    # Wait for auto-pause.
    time.sleep(0.4)
    payload = json.loads(sched_path.read_text(encoding="utf-8"))
    assert payload.get("paused") is True
    paused_at_calls = len(invoke_calls)

    # Simulate user clicking "▶ 다시 켜기" — clear paused flag.
    payload.pop("paused", None)
    payload.pop("paused_reason", None)
    payload.pop("paused_consecutive_failures", None)
    payload.pop("paused_at", None)
    sched_path.write_text(json.dumps(payload), encoding="utf-8")

    # Flip outcome to success so the next batch doesn't re-pause and
    # we can confirm ticks resumed.
    invoke_outcome["ok"] = True
    invoke_outcome["sig"] = ""
    time.sleep(0.3)
    sched.stop()

    assert len(invoke_calls) > paused_at_calls, (
        "scheduler should have resumed after paused flag cleared")
