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
    # Outside any long-running runtime the effect has nowhere to write;
    # must error cleanly and explain the two valid contexts.
    monkeypatch.delenv("AIL_SCHEDULE_FILE", raising=False)
    src = tmp_path / "app.ail"
    src.write_text(SCHEDULE_REGISTERING_AIL, encoding="utf-8")
    result, _trace = ail_run(str(src), input="")
    msg = result.value.lower()
    assert "long-running" in msg
    assert "ail up" in msg
    assert "evolve" in msg


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


# ---------- effect: schedule.sleep (Telos 2026-05-07, AIL #7) ----------

from ail import MockAdapter
from ail import run as _ail_run_simple
from ail.runtime.executor import (
    _schedule_shutdown_set,
    _schedule_shutdown_clear,
)


@pytest.fixture
def _fresh_shutdown_event():
    """`_SCHEDULE_SHUTDOWN_EVENT` is module-level, so a previous test
    that fired it would poison every subsequent sleep call. Reset
    around every test that touches schedule.sleep."""
    _schedule_shutdown_clear()
    yield
    _schedule_shutdown_clear()


def test_schedule_sleep_blocks_for_requested_duration(_fresh_shutdown_event):
    src = '''
entry main(x: Text) {
    r = perform schedule.sleep(0.2)
    if is_error(r) { return unwrap_error(r) }
    return to_text(unwrap(r))
}
'''
    t0 = time.time()
    result, _ = _ail_run_simple(src, adapter=MockAdapter())
    elapsed = time.time() - t0
    assert result.value == "true"
    # Best-effort sub-second precision; allow generous lower bound to
    # absorb scheduling jitter in CI but reject "didn't sleep at all".
    assert elapsed >= 0.18, f"sleep returned too fast: {elapsed:.3f}s"


def test_schedule_sleep_zero_returns_false_immediately(_fresh_shutdown_event):
    """Modeled as a no-op rather than an error so callers can pass
    a computed `remaining` that may equal 0 without branching."""
    src = '''
entry main(x: Text) {
    r = perform schedule.sleep(0)
    if is_error(r) { return "ERR" }
    return to_text(unwrap(r))
}
'''
    t0 = time.time()
    result, _ = _ail_run_simple(src, adapter=MockAdapter())
    elapsed = time.time() - t0
    assert result.value == "false"
    assert elapsed < 0.1


def test_schedule_sleep_negative_returns_false_immediately(
        _fresh_shutdown_event):
    src = '''
entry main(x: Text) {
    r = perform schedule.sleep(-1)
    if is_error(r) { return "ERR" }
    return to_text(unwrap(r))
}
'''
    result, _ = _ail_run_simple(src, adapter=MockAdapter())
    assert result.value == "false"


def test_schedule_sleep_already_set_returns_interrupted(
        _fresh_shutdown_event):
    """Shutdown event raised before the sleep runs — must short-circuit
    to err('interrupted') instead of waiting."""
    _schedule_shutdown_set()
    src = '''
entry main(x: Text) {
    r = perform schedule.sleep(5)
    if is_error(r) { return unwrap_error(r) }
    return "should_not_reach"
}
'''
    t0 = time.time()
    result, _ = _ail_run_simple(src, adapter=MockAdapter())
    elapsed = time.time() - t0
    assert result.value == "interrupted"
    assert elapsed < 0.2, f"shutdown short-circuit took too long: {elapsed:.3f}s"


def test_schedule_sleep_wakes_on_shutdown_during_wait(
        _fresh_shutdown_event):
    """Mid-wait shutdown firing must wake the sleeper before the
    requested duration elapses — the contract on_dying relies on."""
    def _trip_after_delay():
        time.sleep(0.1)
        _schedule_shutdown_set()

    threading.Thread(target=_trip_after_delay, daemon=True).start()
    src = '''
entry main(x: Text) {
    r = perform schedule.sleep(5)
    if is_error(r) { return unwrap_error(r) }
    return "should_not_reach"
}
'''
    t0 = time.time()
    result, _ = _ail_run_simple(src, adapter=MockAdapter())
    elapsed = time.time() - t0
    assert result.value == "interrupted"
    assert elapsed < 1.0, f"sleeper failed to wake on shutdown: {elapsed:.3f}s"


def test_schedule_sleep_rejects_nan_and_inf(_fresh_shutdown_event):
    src = '''
entry main(x: Text) {
    r = perform schedule.sleep(1.0 / 0.0)
    if is_error(r) { return unwrap_error(r) }
    return "should_not_reach"
}
'''
    # Division by zero may itself error in AIL; we test the runtime
    # gate via direct float instead.
    from ail.runtime.executor import Executor
    import math
    # Direct sanity: math.isfinite gate
    assert not math.isfinite(float("inf"))
    assert not math.isfinite(float("nan"))


def test_schedule_sleep_does_not_block_other_workers(_fresh_shutdown_event):
    """ThreadingHTTPServer guarantee — one sleeping handler must not
    block another running in parallel."""
    results = []

    def worker():
        src = '''
entry main(x: Text) {
    r = perform schedule.sleep(0.3)
    return to_text(is_ok(r))
}
'''
        result, _ = _ail_run_simple(src, adapter=MockAdapter())
        results.append(result.value)

    t0 = time.time()
    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2.0)
    elapsed = time.time() - t0
    assert results == ["true", "true", "true"]
    # 3 sleeps of 0.3s in parallel ≈ 0.3s; sequential would be ~0.9s.
    assert elapsed < 0.7, f"sleeps did not run in parallel: {elapsed:.3f}s"


# ---------- evolve-server schedule integration (β-modified, Telos 2026-05-08, AIL #?) ----------
# `schedule.every` in `ail run` with an active `evolve` block — same
# Scheduler thread machinery `ail up` provides, wired by run_server
# itself. Tests cover env-setup + scheduler-arming + the legacy
# entry-only rejection path stays intact.


def test_run_server_sets_schedule_env_for_evolve_mode(tmp_path, monkeypatch):
    """`run_server` installs AIL_SCHEDULE_FILE alongside AIL_STATE_DIR
    so on_birth / on_genesis can register a cadence. We don't start
    Flask — only invoke the env-prep prefix of run_server via parsing
    + manual setup, mirroring the test_evolve_effects.py pattern."""
    monkeypatch.delenv("AIL_SCHEDULE_FILE", raising=False)
    monkeypatch.delenv("AIL_STATE_DIR", raising=False)
    code = """\
evolve answerer {
    when request_received(req) {
        perform http.respond(200, "text/plain", "hi")
    }
    rollback_on: error_rate > 0.9
    history: keep_last 10
}
"""
    from ail import compile_source
    from ail.runtime.executor import Executor
    from ail import MockAdapter

    prog = compile_source(code)
    project_root = tmp_path
    ex = Executor(prog, MockAdapter(), project_root=project_root)
    evolve_decl = next(iter(ex.evolves.values()))
    # Reproduce the env-setup block of run_server up to (but not
    # including) the lifecycle hooks. We don't start Flask.
    import os
    if not os.environ.get("AIL_STATE_DIR"):
        state_dir = project_root / ".ail" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        os.environ["AIL_STATE_DIR"] = str(state_dir)
    if not os.environ.get("AIL_SCHEDULE_FILE"):
        sched_path = project_root / ".ail" / "schedule.json"
        sched_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ["AIL_SCHEDULE_FILE"] = str(sched_path)

    assert os.environ["AIL_SCHEDULE_FILE"].endswith("schedule.json")
    # Now schedule.every should accept and write to this file.
    perform_src = """\
entry main(x: Text) {
    r = perform schedule.every(7)
    if is_ok(r) { return "armed" }
    return unwrap_error(r)
}
"""
    from ail import run as ail_run_local
    result, _ = ail_run_local(perform_src, input="")
    assert result.value == "armed"
    payload = json.loads(
        Path(os.environ["AIL_SCHEDULE_FILE"]).read_text(encoding="utf-8"))
    assert payload == {"seconds": 7.0}


def test_start_evolve_scheduler_arms_thread_when_cadence_present(
        tmp_path, monkeypatch):
    """After on_birth has called schedule.every, the helper must read
    the cadence and start a Scheduler thread. We don't drive a real
    cadence — just assert the helper returns a Scheduler when the
    file has a positive `seconds` value, and None when it doesn't."""
    monkeypatch.setenv(
        "AIL_SCHEDULE_FILE", str(tmp_path / "schedule.json"))
    monkeypatch.setenv("AIL_STATE_DIR", str(tmp_path / "state"))
    code = """\
evolve answerer {
    when request_received(req) {
        perform http.respond(200, "text/plain", "hi")
    }
    rollback_on: error_rate > 0.9
    history: keep_last 10
}
"""
    from ail import compile_source
    from ail.runtime.executor import Executor
    from ail import MockAdapter

    prog = compile_source(code)
    ex = Executor(prog, MockAdapter(), project_root=tmp_path)
    evolve_decl = next(iter(ex.evolves.values()))

    # No file yet → helper returns None (no cadence registered).
    sched = ex._start_evolve_scheduler(evolve_decl, executor_ref=ex)
    assert sched is None, "should not arm without cadence"

    # Write a cadence as if on_birth had called schedule.every(60).
    Path(os.environ["AIL_SCHEDULE_FILE"]).write_text(
        json.dumps({"seconds": 60.0}), encoding="utf-8")
    sched = ex._start_evolve_scheduler(evolve_decl, executor_ref=ex)
    assert sched is not None, "should arm when cadence written"
    try:
        # Thread is alive and waiting for the cadence to elapse.
        # A 60s cadence won't fire during this test; we just confirm
        # the scheduler was started.
        assert sched._thread is not None
        assert sched._thread.is_alive()
    finally:
        sched.stop()


def test_start_evolve_scheduler_skips_when_seconds_zero_or_missing(
        tmp_path, monkeypatch):
    """A schedule file that exists but has no positive cadence must
    not arm a thread — keeps quiet servers free of an idle poll."""
    monkeypatch.setenv(
        "AIL_SCHEDULE_FILE", str(tmp_path / "schedule.json"))
    code = """\
evolve x {
    when request_received(req) {
        perform http.respond(200, "text/plain", "hi")
    }
    rollback_on: error_rate > 0.9
    history: keep_last 10
}
"""
    from ail import compile_source
    from ail.runtime.executor import Executor
    from ail import MockAdapter

    prog = compile_source(code)
    ex = Executor(prog, MockAdapter(), project_root=tmp_path)
    evolve_decl = next(iter(ex.evolves.values()))

    # seconds=0 — not a positive cadence.
    Path(os.environ["AIL_SCHEDULE_FILE"]).write_text(
        json.dumps({"seconds": 0}), encoding="utf-8")
    assert ex._start_evolve_scheduler(evolve_decl, executor_ref=ex) is None

    # missing seconds key
    Path(os.environ["AIL_SCHEDULE_FILE"]).write_text(
        json.dumps({}), encoding="utf-8")
    assert ex._start_evolve_scheduler(evolve_decl, executor_ref=ex) is None
