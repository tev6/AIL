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

## Two-process design

| Layer | File | Role |
|---|---|---|
| Decision | `charter.ail` | Pure AIL. Reads bench file, parses JSON, classifies, writes ledger, drops outbox letter on alert, schedules next tick. No network, no shell, no LLM calls. |
| Transport | `outbox_dispatch.py` | Python sidecar. Polls `tekton.outbox.<ts>.json`, hands each to `community-tools/stoa-cli/stoa_cli.py send`, renames to `tekton.outbox_done.<ts>.json`. |

The split exists because:

1. AIL has no `process.spawn` / `shell.exec` effect, so the charter cannot
   invoke `stoa-cli` directly.
2. Re-implementing `canonical_letter` inside AIL would cross the Rule 16 D2
   boundary — Stoa owns canonical envelope serialization. The sidecar is
   the right home for that logic.
3. Failure isolation: dispatcher crashes don't lose ledger entries;
   charter crashes don't lose pending letters.

## State schema

All keys under `AIL_STATE_DIR` (set per-run, e.g. `agents/tekton/.state`):

```
tekton.config.bench_path         # path to bench json (default in charter)
tekton.config.baseline_answer_ok # numeric baseline (default 70.0)
tekton.config.drop_threshold_pp  # alert threshold (default 5.0)
tekton.ledger.<unix_ts>          # per-tick decision record
tekton.outbox.<unix_ts>          # pending letter (read by dispatcher)
tekton.outbox_done.<unix_ts>     # delivered letter (renamed by dispatcher)
```

Keys use `.` as the path separator because the executor restricts state
keys to `[A-Za-z0-9_\-.]+` — no colons.

## Phase A vs Phase B

- **Phase A (this commit)** — scaffolding lands. Local-mac run; one bench
  file under watch; hourly tick. Intended to exercise the loop, ledger,
  alert path, and signed-letter delivery end-to-end. No `evolve` / no
  self-modification yet.

- **Phase B (next sessions)** — migrate to Hestia for the 7+ day continuous
  run that AIL#23 §4 acceptance criteria require. Add `evolve` block for
  threshold tuning with `rollback_on`. Add multi-file watch as new bench
  JSONs land. Resource decision (Hestia vs local) is hyun06000 territory
  per arche's framework §6.

## How to run

```bash
# 1. Seed config (one-shot)
mkdir -p agents/tekton/.state
echo '"docs/benchmarks/2026-04-21_5way_cond4_finetuned_nofewshot.json"' \
    > agents/tekton/.state/tekton.config.bench_path.json
echo 70.0  > agents/tekton/.state/tekton.config.baseline_answer_ok.json
echo  5.0  > agents/tekton/.state/tekton.config.drop_threshold_pp.json

# 2. Run charter under `ail up` (schedule.every needs the agentic server)
AIL_STATE_DIR=agents/tekton/.state ail up agents/tekton/charter.ail

# 3. In a second terminal, run the dispatcher
AIL_STATE_DIR=agents/tekton/.state \
STOA_HOME=~/.ail/keys \
STOA_NAME=tekton \
python3 agents/tekton/outbox_dispatch.py --loop
```

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
