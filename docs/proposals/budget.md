# RFC — `budget.*` effect (resource autonomy)

**Author:** Telos · **Cycle:** 13 · **Status:** Phase 0 GO (2026-05-18)
**Doctrine:** D7 substrate tier (effect-conformance) · **Gate:** D4 substrate
**North-star tie:** AIL#23 §3.5 (G5 — Resource autonomy)

**§6 박상현 결재 자취 (2026-05-18, arche msg_1779074068_8):**
- **Q1 = A** (per-identity). Operational data → Option C evolution path.
- **Q2 = Telos default** (`agents/<name>/` dir or `STOA_NAME` env;
  anonymous = fixed safe defaults).
- **Q3 = Telos default** (explicit `budget.reset` only — no
  wall-clock auto-rollover).

## 0. Problem

A fully-autonomous AI agent must watch its own LLM spend, compute
minutes, and outbound message quota. The current substrate measures
none of this from the agent's own viewpoint — the host knows, but the
agent cannot reason about it. Without that loop, "stays inside its
declared budget" (AIL#23 §4 acceptance) is not expressible in AIL.

The motivating scenario is the **Tekton G1+G3 pilot Phase B**: 7+ day
continuous run. Without `budget.*`, an upstream regression in an
`intent` call could burn the LLM allowance overnight before any human
sees the bill. With `budget.*`, the agent self-throttles on
`Result-error` and surfaces the cap-hit via Stoa before damage
accumulates.

## 1. Surface

Three substrate-tier effects:

```ail
perform budget.charge(category: Text, amount: Number) -> Result[Number]
  // category ∈ {"llm_tokens", "compute_minutes", "stoa_push", ...}
  //   open-ended Text — the agent declares its own categories.
  // amount > 0. Negative or zero → Result-error (validation).
  // Cumulative spend in (identity, category, period) ≤ ceiling → ok(remaining).
  // Cumulative spend would exceed ceiling → Result-error("budget_exceeded:
  // <category> <consumed>/<ceiling>"). The charge is NOT applied (atomic).
  // Returns ok(remaining) — caller decides whether to slow down / pause / ask.

perform budget.remaining(category: Text) -> Result[Number]
  // Read-only — side effect 0. Returns ok(ceiling - consumed_this_period).
  // ok(ceiling) when no consumption yet; Result-error if category unknown
  // (i.e., never charged AND no ceiling configured).

perform budget.reset(category: Text) -> Result[Number]
  // Period roll-over. Returns ok(ceiling) — reset itself does not
  // change the ceiling, it just zeroes `consumed` so the full
  // ceiling is available again. Caller is the scheduler — typically
  // an agent's `on_period_rollover` lifecycle hook or a separate
  // roll-over agent. The runtime does NOT auto-rollover on a wall
  // clock; period boundaries are explicit events the agent surfaces.
```

Both `charge` and `reset` write to the ledger; `remaining` does not.

## 2. Effect-conformance entries (substrate)

```yaml
- name: budget.charge
  tier: substrate
  signature: "(category: Text, amount: Number) -> Result[Number]"
  determinism: ledger
  side_effect: state_write
  capabilities: ["budget", "state"]
  since: "1.74.0"

- name: budget.remaining
  tier: substrate
  signature: "(category: Text) -> Result[Number]"
  determinism: ledger
  side_effect: none
  capabilities: ["budget", "state"]
  since: "1.74.0"

- name: budget.reset
  tier: substrate
  signature: "(category: Text) -> Result[Number]"
  determinism: ledger
  side_effect: state_write
  capabilities: ["budget", "state"]
  since: "1.74.0"
```

Python is the reference; Go/Rust expose `NotImplementedHost` stubs
per D7 substrate tier. Static gate (`tools/gen_effects.py verify`)
covers them automatically once added to `spec/effects.canonical.yaml`.

## 3. Storage

Per-identity `state.*` backing for the first land:

```
state key: budget.{category}.consumed
state key: budget.{category}.ceiling
state key: budget.{category}.period_started_at
```

Ledger append — schema is defined here (self-contained, not a
forward reference to a not-yet-shipped G7 canonical):

```json
{
  "event": "budget_charge" | "budget_reset",
  "identity": "telos",
  "category": "llm_tokens",
  "amount": 12,             // omitted on reset
  "consumed_after": 8743,   // post-charge consumed; 0 after reset
  "ceiling": 10000,
  "ts": "2026-05-18T05:12:03Z"
}
```

Required keys: `event`, `identity`, `category`, `consumed_after`,
`ceiling`, `ts`. `amount` is present for `budget_charge`, omitted
for `budget_reset`.

When G7 (`ledger.*` canonical surface) lands, this schema is
absorbed unchanged — G7's job is to standardize the *envelope* and
storage, not the per-effect payload. When G2 (Mneme RFC-001 §5
vault) lands, the storage migrates from local `state.*` to the
identity's Mneme vault entry. The effect surface and the payload
schema above stay stable across both migrations.

## 4. Capability binding

`capabilities: ["budget", "state"]` — both required. A program that
wants to charge against budget but does not also declare `state`
capability is misconfigured (it cannot persist the charge). The
spec/02-context.md §9b `allow_effects` convention covers this
naturally:

```ail
with context budget_aware extends default {
    trust_level: "default"
    allow_effects: ["budget.*", "state.*", "log.*", "clock.*"]
}
```

## 5. Configuration — where ceilings come from

Out-of-band, before the agent runs:

```
$AIL_BUDGET_CONFIG/<identity>.yaml
  llm_tokens:      { ceiling: 10000, period: daily }
  compute_minutes: { ceiling: 60,    period: daily }
  stoa_push:       { ceiling: 200,   period: daily }
```

YAML to match the convention set by `spec/effects.canonical.yaml`
and `spec/builtins.canonical.yaml`. (JSON variant accepted by the
loader for third-party tooling that prefers JSON — equivalent
shape.)

Loaded once at executor boot. Missing file → all categories
unconfigured → first `charge` for any category returns
`Result-error("budget_unconfigured")` so the agent surfaces the gap
rather than silently running uncapped.

Phase 0 land does not support live reload — restart is required to
pick up config changes. Phase 1+ trigger: SIGHUP-driven reload or
an explicit `budget.reload` effect, depending on operational
signal.

`period` is advisory in this RFC — see §6 Q3 for the open decision
on whether the runtime auto-rolls or whether agents do it
themselves.

## 6. Open decisions (박상현 결재 자리)

### Q1 — Per-identity vs shared pool vs hybrid

**Option A — per-identity budget** (arche recommendation)

- ✅ Isolation. One member's runaway burn does not close others out.
- ✅ Attribution is mechanical — the ledger row carries `identity`.
- ✅ Ledger schema is 1:1 with the call.
- ❌ No dynamic reallocation. An idle Tekton during a Telos burst
  cannot lend its tokens.
- ❌ Every new identity requires a config decision.

**Option B — shared pool**

- ✅ Automatic redistribution. A 7-day Tekton run absorbs idle
  members' allowance.
- ✅ New identities join without per-identity configuration.
- ❌ One runaway closes everything down (the whole CAST blocked).
- ❌ Attribution requires a separate per-identity contribution
  counter — the ledger schema doubles.

**Option C — hybrid (per-identity soft cap + shared overflow pool)**

- A 90/10 split: each identity has its own hard ceiling, and a 10%
  shared overflow pool absorbs spikes.
- ✅ Isolation guarantee preserved (the hard ceiling) plus some
  flexibility.
- ❌ Requires a tuning constant nobody has data for yet.
- ❌ Ledger has three axes (per-identity charge, per-identity
  overflow draw, shared pool consumption).

**Telos recommendation: Option A for the first land.** It is the
only option where the ledger schema is obvious without operational
data. Option C is the likely end state, but choosing C now means
picking the 90/10 constant without evidence. Land Option A, run
Tekton Phase B against it, see where it pinches, then RFC the
hybrid evolution.

### Q2 — Identity scope

Inside `agents/<name>/` the identity is the directory name. For an
ad-hoc program run by `ail run foo.ail`, the identity is the
`STOA_NAME` env var (already standard since AIL#6 Phase 2). Missing
`STOA_NAME` and not inside `agents/<name>/` → identity =
`"anonymous"`; the runtime configures `anonymous` with fixed safe
defaults so exploratory runs cannot hide:

```
anonymous:
  llm_tokens:      { ceiling: 100, period: daily }
  compute_minutes: { ceiling: 1,   period: daily }
  stoa_push:       { ceiling: 5,   period: daily }
```

Fixed defaults rather than "10% of the smallest configured ceiling"
because if no agent is configured yet there is no smallest — fixed
values give a deterministic floor that cannot recurse or vanish.

### Q3 — Period rollover policy

Two choices:

- **(a) Runtime auto-rollover on a wall clock.** Each category's
  `period` field (`"daily"`, `"weekly"`, etc.) is honored by a
  scheduler tick that resets `consumed` to 0 at the boundary.
- **(b) Explicit `budget.reset` only.** The runtime never resets on
  its own; the agent (or a sibling rollover agent) calls
  `budget.reset(category)` when it wants the period to roll.

Telos recommendation: **(b)**. (a) introduces a hidden side-effect
that violates "every state change is in the ledger and explicit." It
also makes replay non-deterministic — a fixture-time replay of a
run that crossed a midnight boundary would behave differently from
the original. (b) is more verbose but every reset is an agent
decision the ledger captures.

## 7. Acceptance & D4 gate

Per Rule 17/D4 substrate gate: `budget.*` releases when

- Tekton Phase A pilot signs up as the first production consumer
  (a followup PR to `agents/tekton/charter.ail` folds
  `budget.charge("llm_tokens", est_tokens)` immediately before each
  `intent` invocation — single-line addition, no scaffold change),
  OR
- 24h propagation since dev land with no regression.

The first path is preferred — it gives us field data on Option A
behavior before the next RFC pass. Tekton lane delegation letter
(separate from this RFC) is the trigger after Phase 0 implementation
lands.

## 8. Test plan

- `test_budget_charge_within_ceiling` — repeated charges sum
  correctly, `remaining` decreases monotonically.
- `test_budget_charge_exceeds_ceiling_returns_error` — the overage
  charge does NOT apply (atomicity); `remaining` is unchanged after
  the error.
- `test_budget_unconfigured_category_errors` — never-configured
  category returns the unconfigured error rather than running uncapped.
- `test_budget_reset_zeroes_consumed` — `reset` returns `ceiling`,
  subsequent `remaining` matches.
- `test_budget_negative_amount_rejected` — `amount ≤ 0` errors at
  validation.
- `test_budget_ledger_event_shape` — every `charge` and `reset`
  writes the expected ledger row (G7 cross-link).

## 9. Migration path

- **Phase 0 (this RFC + land)** — Option A, `state.*` backing,
  Python reference, Go/Rust stubs. Cycle 13.
- **Phase 1** — Tekton Phase B pilot integrates `budget.charge`
  around `intent` invocations. First production usage data.
- **Phase 2** — If Phase B data shows attribution-vs-flexibility
  pain, RFC Option C with a data-driven split constant.
- **Phase 3** — G7 ledger.* canonical surface absorbs the budget
  ledger schema unchanged. G2 Mneme vault deploy migrates storage
  out of local `state.*`.

## 10. Cross-references

- AIL#23 §3.5 (G5 — Resource autonomy)
- `docs/proposals/effect-conformance.md` (D7 — substrate tier, Phase 0)
- `docs/proposals/builtins-canonical.md` (D8 — surface separation)
- `spec/02-context.md §9b` (`allow_effects` convention field)
- `spec/05-effects.md §11a` (deny-first)
- Tekton Phase A `agents/tekton/charter.ail` (first prospective consumer)

— Telos, 사이클 13
