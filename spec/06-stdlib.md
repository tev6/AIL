# AIL Specification — 06: Standard Library

**Version:** 0.2 — implementation-accurate (Telos 2026-05-14, AIL #19)

The standard library is a curated set of intents and pure helpers that every conforming runtime ships. It is deliberately small — programs should be able to do useful work without redefining basic building blocks, and AI authors should be able to learn the full surface in a single pass.

Items are grouped by module. A program imports a name:

```ail
import summarize from "stdlib/language"
import word_count from "stdlib/utils"
```

The current runtime ships **four modules**: `stdlib/core`, `stdlib/language`, `stdlib/utils`, `stdlib/agent`. Earlier drafts listed six more modules (`reason`, `effects`, `time`, `trace`, `confidence`, `planner`) — those are *not implemented* and are documented in §6 below as future work, not as part of the conforming surface.

---

## 1. `stdlib/core`

Foundational intents that every program can rely on.

### Intents

- **`identity(x: Text) -> Text`** — returns `x`. Useful as a default target in `branch` or as a baseline in evolve harnesses.
- **`refuse(reason: Text) -> Text`** — aborts the current intent with a declared refusal reason. Recorded in trace; distinct from a failure.

### Contexts and types

Contexts (`default`, `strict`, `exploratory`) and confidence-bearing types (`Distribution`, `Interval`, `Set`) are described in [02-context.md §2](02-context.md) and [03-confidence.md](03-confidence.md). They are part of the language, not separate stdlib modules.

---

## 2. `stdlib/language`

Operations on natural-language text. Every intent here is calibratable and evolvable.

- **`summarize(source: Text, max_tokens: Number) -> Text`** — produces a summary within the token limit. Context-aware (register, audience, weight).
- **`translate(source: Text, target_language: Text) -> Text`** — translates text. Infers source language.
- **`classify(text: Text, labels: Text) -> Text`** — returns the best-matching label from a comma-separated list.
- **`extract(source: Text, schema_description: Text) -> Text`** — structured extraction. Returns a JSON-ish text record.
- **`rewrite(source: Text, instruction: Text) -> Text`** — applies a rewrite instruction.

All five carry adapter-driven LLM calls. `evolve` blocks may wrap any of them to track quality drift.

---

## 3. `stdlib/utils`

Pure functions over text, numbers, and lists. No effects, no LLM calls — callable from `pure fn` bodies. The current set:

### Text

- **`word_count(text: Text) -> Number`** — whitespace-split count.
- **`char_count(text: Text) -> Number`** — character count.
- **`is_empty(text: Text) -> Boolean`** — true for `""` or all-whitespace.
- **`repeat(text: Text, times: Number) -> Text`** — concatenate `text` `times` times.
- **`pad_left(text: Text, target_length: Number, pad_char: Text) -> Text`** — left-pad with a single character.
- **`contains(text: Text, sub: Text) -> Boolean`** — substring presence.
- **`count_occurrences(text: Text, sub: Text) -> Number`** — non-overlapping occurrences.
- **`truncate(text: Text, max: Number) -> Text`** — first `max` characters.
- **`to_upper_first(text: Text) -> Text`** — uppercase the first character.
- **`plural_count(n: Number, singular: Text, plural: Text) -> Text`** — `"1 item"` / `"3 items"` style format.
- **`is_numeric(text: Text) -> Boolean`** — true iff every character is a digit.

### Numbers

- **`clamp(value: Number, lo: Number, hi: Number) -> Number`** — saturate into the range.
- **`sum_list(numbers: [Number]) -> Number`** — total.
- **`average(numbers: [Number]) -> Number`** — mean; empty list returns 0.

### Lists

- **`flatten(nested: [[Any]]) -> [Any]`** — one level of flattening.
- **`unique(items: [Any]) -> [Any]`** — preserve-order dedupe.
- **`zip_lists(a: [Any], b: [Any]) -> [[Any]]`** — pair shortest-of-two.
- **`take(items: [Any], n: Number) -> [Any]`** — first `n` items.

### CSV

- **`csv_to_rows(csv: Text) -> [[Text]]`** — parse a simple comma-separated table (no quoting).
- **`rows_to_csv(rows: [[Text]]) -> Text`** — inverse.

---

## 4. `stdlib/agent`

The three-phase **plan → act → reflect** loop, packaged as three intents. Each intent prompts the adapter to think about one phase only; the program glues them together. This is the canonical shape for agentic programs that need explicit reasoning steps rather than a single end-to-end call.

- **`plan(state: Record) -> Text`** — given the current state (typically a record of inputs, history, goal), return a short plan. Should be re-runnable as new information arrives.
- **`act(plan_description: Text) -> Record`** — execute one step of the plan and return the observable result as a record.
- **`reflect(action_result: Record) -> Record`** — observe the action's outcome and return a record describing what to keep, what to change, and whether the goal is reached.

Both `state` and the records returned by `act` / `reflect` are open-shape — programs decide the fields. Pair with `state.read` / `state.write` for memory across iterations and with `evolve` for quality tracking over many runs.

---

## 5. What is not in the standard library

Deliberately omitted:

- **General-purpose I/O beyond the effects listed in [05-effects.md](05-effects.md).** Ad-hoc I/O invites untraced side effects. The effect surface is the contract — anything outside it does not happen in a conforming program.
- **Concurrency primitives.** The runtime manages concurrency; programs do not fork threads. Long-running work uses `schedule.every` + `on_tick` in evolve-server mode, not stdlib calls.
- **Cryptographic primitives.** Crypto lives at the builtin layer (`crypto_*_ed25519`, `crypto_random_bytes`) — not as stdlib intents — so signatures and key material never pass through an LLM adapter. See [05-effects.md](05-effects.md).
- **Machine-learning training.** AIL is for authoring intent; training is an external activity whose artifacts become models that AIL invokes via the adapter.
- **UI primitives.** Rendering belongs in the host. evolve-server programs write static HTML files (`view.html`) and let the runtime serve them.

A program needing any of these uses a host-provided effect or refuses to run on hosts that do not provide it.

---

## 6. Future modules — not yet implemented

The 0.1 draft listed six additional modules that never landed in the runtime. They are kept here as a known design space rather than as part of the conforming surface, so AI authors writing `import X from "stdlib/Y"` do not hallucinate a module name that the runtime will reject at parse time.

Status as of v1.72.2:

| Module | Status | Notes |
|--------|--------|-------|
| `stdlib/reason` | not implemented | `decompose` / `verify` / `compare` / `critique` / `consensus`. Programs needing these compose them ad-hoc as project-local intents or via `stdlib/agent`'s `plan` + `reflect`. |
| `stdlib/effects` | not implemented | Effect declarations live in [05-effects.md](05-effects.md) as a flat surface — importing them as a stdlib module would duplicate that contract. |
| `stdlib/time` | not implemented | The `clock.now` effect and `schedule.every` / `schedule.sleep` cover the current use cases. `within(deadline, do: Intent)` and `schedule(at: Time, do: Intent)` are open design space. |
| `stdlib/trace` | not implemented | The runtime trace is part of every program automatically; explicit `trace.span` / `trace.attach` would expose it for programmatic inspection. No conforming runtime exposes the trace as a value yet. |
| `stdlib/confidence` | not implemented | Confidence is a first-class value (every `ConfidentValue` carries one); pure helpers `and` / `or` / `not` / `calibrate` / `ece` are spec'd but not bundled. Programs roll their own when needed. |
| `stdlib/planner` | not implemented | `plan(goal: Text) -> Plan` would require a structured `Plan` type the runtime can re-execute. `stdlib/agent` covers the loop with three text-returning intents instead. |

Adding any of these is an RFC-shaped task: the spec section here gets removed from "not yet implemented" status, the runtime ships the implementations, the reference card and authoring prompt are updated in the same PR (CLAUDE.md Rule 5), and the version stamp at the top of this file bumps.

---

The specification ends here. The next document is [../runtime/00-airt.md](../runtime/00-airt.md) — the runtime.
