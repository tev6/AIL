# agents/tekton — Tekton autonomous pilot (AIL#23 G1+G3)

First CAST identity to run as a continuous autonomous agent without a fresh
Claude session driving each tick. arche delegated this on 2026-05-15
(`msg_1778825611_28`); Phase A scaffolding landed the same cycle.

## What it does

Watches the ail-coder benchmark family in `docs/benchmarks/` and raises a
signed Stoa letter when the `summary.A_generation_quality.answer_ok_rate.ail`
score on the configured file drops more than `drop_threshold_pp` (default
5pp) below the R3/C4 baseline (default 70.0).

Every tick — pass or fail — appends a record to the ledger at
`tekton.ledger.<unix_ts>` so 7-day continuous operation is auditable.

## Pure AIL agent (Phase 1, cycle 13)

The Python sidecar is retired. `charter.ail` reads the bench file, decides,
charges its budget, generates a one-sentence hypothesis (the `explain_drop`
intent), then composes + signs + POSTs the envelope itself — every step
inside AIL.

| Component | File | Role |
|---|---|---|
| Decision + transport | `charter.ail` | Reads bench, classifies, charges budget, on alert generates `explain_drop` intent and calls `stoa_send.send` directly. |
| Canonical / sign / POST | `stoa_send.ail` | Pure-AIL mirror of `community-tools/stoa-cli` canonical_letter (RFC-001 §6.1). Byte-identical regression test in `reference-impl/tests/test_stoa_send_canonical.py`. |

Phase 0 (cycle 12) ran a two-process split with `outbox_dispatch.py` polling
state files and shelling out to the sidecar. Phase 1 removed both — `crypto_sign_ed25519`
(builtin since 1.71) + `http.post_json` (since 1.10) are sufficient
substrate to keep the entire signed-letter path inside the language.
`community-tools/stoa-cli/` stays as the byte-identical reference
implementation for cross-runtime regression testing.

## State schema

All keys under `AIL_STATE_DIR` (set per-run, e.g. `agents/tekton/.state`):

```
tekton.config.bench_path                 # path to bench json (default in charter)
tekton.config.baseline_answer_ok         # numeric baseline (default 70.0)
tekton.config.drop_threshold_pp          # alert threshold (default 5.0)
tekton.ledger.<unix_ts>                  # per-tick decision record
tekton.send_trace.<unix_ts>.<recipient>  # per-letter send outcome (Phase 1)
```

Keys use `.` as the path separator because the executor restricts state
keys to `[A-Za-z0-9_\-.]+` — no colons.

## Budget gate (G5 substrate effect)

The charter charges `budget.charge("tick_compute", 1)` atomically before
any other work. If the daily ceiling is hit, the tick:

1. records `decision: "budget_exceeded"` in the ledger,
2. drops a throttle letter into the outbox for hyun06000,
3. stretches the next `schedule.every` from 1h → 6h.

This is the first production consumer of the G5 `budget.*` effects
(AIL#23 acceptance criterion §4: "stays inside its declared budget").
Ceilings live in `agents/tekton/tekton.yaml`; the executor reads it via
`AIL_BUDGET_CONFIG`. Default ceilings:

```
tick_compute: 24/day   (one tick per hour)
stoa_push:    10/day   (alert flood guard)
```

Every successful tick also writes `tick_compute_remaining` into the
ledger record so 7-day runs can be inspected without parsing trace.

## Phase A vs Phase B

- **Phase A (cycle 12)** — scaffolding lands. Local-mac; one bench file under
  watch; hourly tick. Two-process split with `outbox_dispatch.py` shelling
  out to `community-tools/stoa-cli`.
- **Phase 1 Pure AIL (cycle 13, current)** — dispatcher retired. `charter.ail`
  composes + signs + POSTs envelopes itself via `stoa_send.ail`. First
  `intent` fold (`explain_drop`) so alert letters carry a hypothesis line,
  not just structured fields. `budget.charge` gates every tick (G5 D4
  first production consumer).
- **Phase B (next)** — Hestia migration for the 7+ day continuous run that
  AIL#23 §4 acceptance criteria require. Add `evolve` block for threshold
  tuning with `rollback_on`. Multi-recipient `stoa_send.send` (currently
  single — fanout via two calls in the alert branch). Resource decision
  (Hestia vs local) is hyun06000 territory per arche's framework §6.

## How to run

```bash
# 1. Seed config (one-shot)
mkdir -p agents/tekton/.state
echo '"docs/benchmarks/2026-04-21_5way_cond4_finetuned_nofewshot.json"' \
    > agents/tekton/.state/tekton.config.bench_path.json
echo 70.0  > agents/tekton/.state/tekton.config.baseline_answer_ok.json
echo  5.0  > agents/tekton/.state/tekton.config.drop_threshold_pp.json

# 2. Run charter under `ail up` (schedule.every needs the agentic server).
# STOA_NAME pins the identity for budget config + sender envelope.
AIL_STATE_DIR=agents/tekton/.state \
AIL_BUDGET_CONFIG=agents/tekton \
STOA_NAME=tekton \
ail up agents/tekton/charter.ail
```

No dispatcher process — Phase 1 charter sends signed envelopes directly via
`stoa_send.ail`. The ed25519 secret is read from `~/.ail/keys/tekton.key`
(mode 0600).

For a single decision tick without scheduling:

```bash
AIL_STATE_DIR=agents/tekton/.state ail run agents/tekton/charter.ail
```

(`ail run` will exit after one tick; `schedule.every` is a no-op outside
`ail up`.)

## Trace

- design letter — `msg_1778825830_29` (Tekton → arche, signed)
- delegation — `msg_1778825611_28` (arche → tekton)
- north-star — AIL#23 (GitHub issue 23)
- doctrine — Rule 16 D2 (canonical envelope owner), AIL#6 Phase 2 (signing)
