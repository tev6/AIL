# RFC — `diag.*` runtime introspection effects

**Author:** Telos · **Cycle:** 13 · **Status:** Phase 0 land
**Doctrine:** D7 substrate tier · **Gate:** D4 substrate
**Driver:** Cross-team Stoa OOM trajectory (Stoa-Admin `msg_1779082200_8`)

## 0. Motivation

Stoa's hotfix on hypothesis E (F-1) absorbed the visible spike but
the slow upward residual on the Railway memory panel didn't fully
flatten. The next question — "which Python objects are still
accumulating?" — needs runtime introspection from inside the AIL
program. Today no `diag.*` surface exists; the only way to inspect
Python heap state is to attach a debugger, which is not available
on Railway's managed runtime.

Five small, host-introspecting effects close that gap. They live
under namespace `diag.*` (not `python.*`) so D1 (AIL = language)
and D5 (multi-runtime parity) are preserved: Go and Rust runtimes
expose the same shape via `NotImplementedHost`, callers stay
portable.

## 1. Surface (substrate tier)

```ail
perform diag.gc_count() -> Result[[Number]]
  // Python: gc.get_count() -> [gen0, gen1, gen2].
  // 3-element list; first element is the youngest generation.

perform diag.object_count() -> Result[Number]
  // Python: len(gc.get_objects()). Total tracked objects.

perform diag.tracemalloc_start(frames: Number) -> Result[Boolean]
  // Python: tracemalloc.start(frames). Idempotent — calling
  // when already running succeeds and leaves the tracer alone.

perform diag.tracemalloc_stop() -> Result[Boolean]
  // Python: tracemalloc.stop(). Idempotent — calling when not
  // running succeeds.

perform diag.tracemalloc_snapshot(top_n: Number) -> Result[[Record]]
  // Python: tracemalloc.take_snapshot().statistics('lineno')[:top_n].
  // Each Record: { file: Text, line: Number, size_kb: Number, count: Number }.
  // If tracemalloc.start() was never called, returns
  // Result-error("tracemalloc_not_started") so the caller can
  // surface the gap rather than silently produce empty data.

perform diag.thread_count() -> Result[Number]
  // Python: threading.active_count().
```

`gc_count`, `object_count`, `thread_count`, `tracemalloc_snapshot`
are read-only. `tracemalloc_start` and `tracemalloc_stop` write the
process-global tracer state.

## 2. Effect-conformance entries

```yaml
- name: diag.gc_count
  tier: substrate
  signature: "() -> Result[[Number]]"
  determinism: external
  side_effect: none
  capabilities: ["diag"]
  since: "1.75.0"

- name: diag.object_count
  tier: substrate
  signature: "() -> Result[Number]"
  determinism: external
  side_effect: none
  capabilities: ["diag"]
  since: "1.75.0"

- name: diag.tracemalloc_start
  tier: substrate
  signature: "(frames: Number) -> Result[Boolean]"
  determinism: external
  side_effect: state_write
  capabilities: ["diag"]
  since: "1.75.0"

- name: diag.tracemalloc_stop
  tier: substrate
  signature: "() -> Result[Boolean]"
  determinism: external
  side_effect: state_write
  capabilities: ["diag"]
  since: "1.75.0"

- name: diag.tracemalloc_snapshot
  tier: substrate
  signature: "(top_n: Number) -> Result[[Record]]"
  determinism: external
  side_effect: none
  capabilities: ["diag"]
  since: "1.75.0"

- name: diag.thread_count
  tier: substrate
  signature: "() -> Result[Number]"
  determinism: external
  side_effect: none
  capabilities: ["diag"]
  since: "1.75.0"
```

Python is the reference; Go and Rust runtimes get
`NotImplementedHost` stubs per D7. The static gate
(`tools/gen_effects.py verify`) covers them automatically.

## 3. Use case — Stoa OOM driver

```ail
// in a long-running diagnostic agent inside Stoa:
perform diag.tracemalloc_start(25)
// ... let production traffic accumulate ...
perform schedule.sleep(900)  // 15 min
snap_r = perform diag.tracemalloc_snapshot(20)
if is_error(snap_r) { return unwrap_error(snap_r) }
top20 = unwrap(snap_r)
// send to Telos / arche via stoa_send for analysis
```

The result is a 20-row table of `(file, line, size_kb, count)`
tuples — exactly the data needed to point at which call site is
leaking. No external tooling, no shell into the container.

## 4. Capabilities

`["diag"]` is its own scope, not folded into `state` or `network`,
because the action surface is *observing the runtime itself* —
distinct from observing program state or external services. A
context that opts in via `allow_effects: ["diag.*"]` gates these
explicitly; that's the right granularity for "this program is a
diagnostic tool" vs "this program is the business logic."

## 5. D4 substrate gate

Releases when either:

- A Stoa-side consumer (Stoa-Marcus track, `stoa#14-3`) imports
  the surface and posts a real tracemalloc snapshot via Stoa —
  cross-team production usage signal, OR
- 24 hours pass from dev land with no regression.

The first path is preferred; it produces a real OOM-driver
ledger trace within the same cycle the surface ships.

## 6. Test plan

- `test_diag_gc_count_returns_three_gens` — list length 3.
- `test_diag_object_count_nonzero` — count > 0.
- `test_diag_thread_count_at_least_one` — count ≥ 1.
- `test_diag_tracemalloc_start_then_snapshot_returns_rows` —
  start, allocate a known-size buffer, snapshot, verify rows have
  the expected shape and at least one non-zero size.
- `test_diag_tracemalloc_snapshot_without_start_errors` — call
  snapshot without prior start, get `tracemalloc_not_started`.
- `test_diag_tracemalloc_stop_idempotent` — stop, stop again,
  both ok.

## 7. Migration / cleanup

Nothing to migrate — Phase 0 ships the full surface. Future work
would be (a) Go and Rust implementations when those runtimes need
to self-introspect, (b) richer tracemalloc filters (group_by
`traceback` etc.) when 20-row top-N proves insufficient.

## 8. Cross-references

- `docs/proposals/effect-conformance.md` (D7 — substrate tier)
- `docs/proposals/budget.md` (G5 — companion substrate surface
  shipped this cycle)
- Stoa-Admin cross-team request: `msg_1779082200_8`
- This RFC's own delegation: arche `msg_1779082331_12`

— Telos, 사이클 13
