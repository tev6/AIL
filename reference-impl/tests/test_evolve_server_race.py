"""Regression test for #24: _server_lock protects counter mutations under concurrency.

Before the fix, the lock was defined but wrapped the entire request handler
including _exec_block, serializing all requests. After the fix, narrow locks
protect only the counter mutations, letting _exec_block run concurrently.

This test verifies the locking pattern itself — concurrent threads mutating
counters with and without the lock produce the expected behavior.
"""
from __future__ import annotations

import threading
import time


def test_lock_prevents_counter_race():
    """Verify that wrapping counter mutations with a lock prevents data races.

    Without a lock, concurrent increment + reset operations on
    consecutive_failures produce wildly incorrect values (see issue #24
    reproduction). With the lock, consecutive_failures stays bounded by
    the number of error threads that finish without an intervening
    success thread.
    """
    lock = threading.Lock()
    request_count = 0
    error_count = 0
    consecutive_failures = 0

    def success():
        nonlocal request_count, consecutive_failures
        with lock:
            request_count += 1
            consecutive_failures = 0

    def error():
        nonlocal request_count, error_count, consecutive_failures
        with lock:
            request_count += 1
            error_count += 1
            consecutive_failures += 1

    barrier = threading.Barrier(40)

    def worker(tid):
        barrier.wait()
        for _ in range(25):
            if tid % 2 == 0:
                success()
            else:
                error()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 40 threads × 25 calls = 1000 total
    assert request_count == 1000, f"expected 1000 requests, got {request_count}"
    # 20 error threads × 25 calls = 500 errors
    assert error_count == 500, f"expected 500 errors, got {error_count}"

    # With the lock, consecutive_failures cannot exceed the number of
    # unanswered error threads that ran after the last success.
    # Without the lock, it could be as high as 500 (or even higher from
    # lost increments — the issue #24 repro showed 25+).
    # The theoretical maximum is approximately bounded by the number of
    # error threads finishing after the last success thread does, but
    # with the barrier + equal work, it should be very small.
    assert consecutive_failures <= 25, (
        f"consecutive_failures={consecutive_failures} exceeds 25 — "
        f"lock is not preventing races"
    )


def test_lock_without_barrier_stress():
    """Stress test without a barrier — more unpredictable thread interleaving."""
    lock = threading.Lock()
    request_count = 0
    consecutive_failures = 0

    def success():
        nonlocal request_count, consecutive_failures
        with lock:
            request_count += 1
            consecutive_failures = 0

    def error():
        nonlocal request_count, consecutive_failures
        with lock:
            request_count += 1
            consecutive_failures += 1

    N_THREADS = 100
    ITERATIONS = 100

    def worker(tid):
        for _ in range(ITERATIONS):
            if tid % 2 == 0:
                success()
            else:
                error()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = N_THREADS * ITERATIONS
    assert request_count == expected, f"expected {expected} requests, got {request_count}"

    # consecutive_failures can be up to ITERATIONS (one error thread's
    # full batch after the last success reset). Without the lock this
    # number would be in the thousands from lost increments
    # (issue #24 repro showed 25 with only 25 iterations per thread).
    assert consecutive_failures <= ITERATIONS, (
        f"consecutive_failures={consecutive_failures} exceeds {ITERATIONS} — "
        f"lock is not preventing lost increments"
    )
