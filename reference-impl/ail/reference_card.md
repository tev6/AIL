# AIL Reference Card

**Grammar version:** 1.8 · **Frozen:** 2026-04-20 (see [09-stability.md](09-stability.md))

This document is written for AI systems that will read, write, and generate AIL programs. It contains every keyword, every built-in function, every syntax pattern, and concrete input/output examples. No motivational prose. No analogies. Parse this, then write AIL.

This reference card is the canonical grammar surface for the v1.8 freeze. Any change to keyword names, built-in signatures, operator precedence, Result-type API, confidence propagation, or evolve invariants documented below is a grammar-breaking change and requires a major version bump.

---

## FILE EXTENSION

`.ail`

## TOP-LEVEL DECLARATIONS

Every `.ail` file is a sequence of these declarations in any order:

```
fn NAME(PARAMS) -> TYPE { BODY }
intent NAME(PARAMS) -> TYPE { GOAL_BLOCK }
context NAME [extends PARENT] { FIELDS }
effect NAME { FIELDS }
evolve NAME { EVOLVE_FIELDS }
entry NAME(PARAMS) { BODY }
import SYMBOL from "SOURCE"
```

A program MUST have exactly one `entry`. All other declarations are optional.

## TYPES

Primitive: `Number`, `Text`, `Boolean`, `Confidence`
Composite: `[T]` (list), `{key: T}` (record), `T | None` (optional)
Function: `fn(T) -> U`

All numbers are 64-bit float. There is no separate integer type.

## fn — DETERMINISTIC FUNCTION

```ail
fn NAME(param1: Type, param2: Type) -> ReturnType {
    // body: assignments, if, for, return, function calls
    return EXPR
}

pure fn NAME(param1: Type) -> ReturnType {
    // body with structural purity contract
    return EXPR
}
```

Properties: no LLM, confidence always 1.0, no side effects, can be recursive.

`pure fn` adds a **static structural contract**, verified at parse time:
- No `perform` statements in the body (no effects).
- No calls to intents (no LLM).
- No calls to non-pure fns.
- No calls to `eval_ail` (runs arbitrary AIL).
- All builtins in `length, split, join, ...` plus `origin_of, lineage_of,
  has_intent_origin` are trusted pure and may be called.

A pure fn's output is guaranteed to have `has_intent_origin(result) == false`
— compile-time proof, not runtime observation. Violating the contract
raises `PurityError` at parse time; the program never runs.

## intent — LLM-BACKED DECLARATION

```ail
intent NAME(param1: Type) -> ReturnType {
    goal: EXPRESSION
    constraints {
        EXPRESSION
        EXPRESSION
    }
    examples {
        ("input") => ("expected output")
    }
    on_low_confidence(threshold: NUMBER) {
        // handler body
    }
    trace: full | partial | none
}
```

Properties: delegates to a language model, returns (value, confidence), can be evolved.

**Return-type harness (v1.10).** The runtime validates every intent
response against the declared `ReturnType`:

- `Text` must be a plain string. A response that parses as a JSON
  dict or list is rejected — the author asked for text, not a data
  payload.
- `Number` must be numeric or a numeric string; booleans are rejected.
- `Boolean` must be true/false or a trivial string (`"true"`, `"yes"`,
  etc.).
- `[T]` must be a list; every element is validated against the inner
  type.
- Outer markdown code fences (```` ```json\n...\n``` ````) are
  stripped before validation — the model doesn't have to know about
  fence conventions.

On mismatch the runtime retries **once** with the rejection reason
added to the constraints. If the retry also fails, the call returns
at **confidence 0** so downstream `attempt` / `branch` / match
confidence-guards can route around the bad value.

Composite types (`Result[T]`, records) are pass-through in v1.10;
tighter validation lands in a later release.

## context — SITUATIONAL ASSUMPTIONS

```ail
context NAME extends PARENT {
    field_name: VALUE
    override field_name: NEW_VALUE
}
```

Activated with: `with context NAME: { BODY }` or `with context NAME: STATEMENT`
Read inside intent/fn: `context.field_name`

## entry — PROGRAM ENTRY POINT

```ail
entry main(input: Text) {
    // body
    return EXPR
}
```

Exactly one per program. Parameters are bound from the caller.

## import

```ail
import SYMBOL from "stdlib/language"
import SYMBOL from "stdlib/utils"
import SYMBOL from "stdlib/core"
```

Current behavior: imports the entire module, not just the named symbol.

## evolve — SELF-MODIFICATION

```ail
evolve INTENT_NAME {
    metric: METRIC_NAME(sampled: RATE)
    when CONDITION {
        retune TARGET: within [LO, HI]
        // OR
        rewrite constraints tighten_numeric_thresholds_by DELTA
        bounded_by {
            TARGET: [MIN, MAX]
        }
    }
    rollback_on: CONDITION
    history: keep_last N
    require review_by: human    // optional for retune, forced for rewrite
}
```

REQUIRED fields: metric, when + action, rollback_on, history. Missing any = compile error.

### evolve-as-server (v0.2)

```ail
evolve SERVER_NAME {
    listen: PORT_NUMBER
    effects: [file.read, file.write, http.respond, email.send]   // infra-layer deny-first
    metric: error_rate
    when request_received(req) {
        result = route_request(req)
        perform http.respond(get(result, 0), get(result, 1), get(result, 2))
    }
    rollback_on: error_rate > 0.5
    history: keep_last 100
}
```

`when request_received(req)` is an event arm — fires on each HTTP request.
`req` fields: `req.method`, `req.path`, `req.body` (Text), `req.args` (Record of query params),
`req.query` (raw query string), `req.headers` (Record of HTTP headers).
`rollback_on` triggers self-termination (§9). `metric` and `when` fields
are still present; `rollback_on` + `history` remain required.

`effects:` declares the effect whitelist for this server (infra-layer deny-first).
Only effects listed here may be `perform`ed. Undeclared effects are denied even if
they appear in the global `ALLOWED_EFFECTS`. When `effects:` is omitted, the
citizen-layer `ALLOWED_EFFECTS` check applies instead.

### Physis — generational evolution (v0.3)

When `rollback_on` fires, the runtime looks for a `pure fn on_death` by
name convention. If found, it calls `on_death(reason, history)` before
shutting down, writes the Testament to `.ail/physis/<name>/current.json`,
and re-execs the process (the next generation). The code stays frozen;
parameters evolve across lifetimes.

```ail
// Called automatically by the runtime on rollback_on fire. No new keyword.
pure fn on_death(reason: Text, history: [Any]) -> Any {
    // summarise history, produce a testament record
    return [
        ["observed_patterns", ["high error rate on /api"]],
        ["advice", "check upstream dependencies"],
        ["params", [["retry_budget", 5]]]
    ]
}

// Called at entry startup to read the predecessor's testament.
entry main(input: Text) {
    t_r = perform inherit_testament()   // Result[Testament]
    if is_ok(t_r) {
        t = unwrap(t_r)
        // t.generation, t.advice, t.params, t.observed_patterns ...
    }
    // is_error(t_r) means genesis — no predecessor.
}
```

Safety damping: if the process dies in < 30 s, the successor is NOT
auto-spawned (operator intervention required). Max 1000 generations.

### Lifecycle hooks (Arche 2026-04-28)

Five fn-name conventions on top of evolve servers. The runtime checks
for each by name and calls it if defined; otherwise skips. Same dispatch
pattern as `on_death` / `on_compact`. State arg is a Record with
`request_count`, `error_count`, `error_rate`, `generation`, `history`.

```ail
fn on_genesis(testament: Any)         // once, before loop. testament is Result —
                                      // is_error() == genesis, unwrap() == inherited.
fn on_birth()                         // once, right after on_genesis.
fn before_tick(state: Any)            // every request, before the `when` block.
fn on_tick(state: Any)                // every request, between before_tick and `when`.
fn after_tick(state: Any)             // every request, after the `when` block.
fn on_dying(reason: Text,             // rollback_on fire, BEFORE on_death.
            history: [Any])           // effects allowed (mneme.save, etc.).
pure fn on_death(reason: Text,        // rollback_on fire, AFTER on_dying.
                 history: [Any])      // pure — testament composition only.
fn on_letter(letter: Any)             // Stoa pushed a letter to /inbox.
                                      // Runtime auto-200's; user `when`
                                      // block is bypassed for the request.
```

Order: `on_genesis(testament) → on_birth() → loop[before_tick(state) →
on_tick(state) → (on_letter(letter) OR `when` block) → after_tick(state)]
→ on_dying(reason, history) → on_death(reason, history)`.

`on_letter` is the Stoa push hook. The runtime detects POST /inbox with
a JSON body containing `from` and `id` (the Stoa letter envelope shape),
parses it, dispatches `on_letter(letter_record)`, and auto-responds with
`{"received": true, "id": <id>}` — so the agent never writes HTTP
routing for letters. Self-letters (`stoa_post(from=self, to=self, ...)`)
flow through the same path: Stoa fans out to your own webhook, on_letter
fires next tick. That closes the soft-reset / self-correction loop —
agents evolve without dying.

The on_dying / on_death split: side effects belong in on_dying (commit
identity, flush logs, send a goodbye); the pure on_death just shapes
the testament. This way the testament composition stays
provenance-clean and the cleanup keeps its full effect surface.

Hooks may be `pure fn` or `fn` — declare effects only on the ones that
need them (e.g. `before_tick` doing inbox poll). A hook that raises is
logged and ignored; the loop never dies because of a broken hook.

## STATEMENTS

```
VARIABLE = EXPRESSION                          // assignment
return EXPRESSION                              // return
if CONDITION { BODY } else if ... { } else { } // deterministic branch
for VARIABLE in COLLECTION { BODY }            // bounded loop (no while)
branch EXPR { [COND] => STMT ... }             // probabilistic branch
with context NAME: { BODY }                    // context activation
perform EFFECT_NAME(ARGS)                      // side effect
VARIABLE = perform EFFECT_NAME(ARGS)           // effect as expression
VARIABLE = attempt { try EXPR; try EXPR; ... } // confidence-priority cascade
VARIABLE = match EXPR { PATTERN => BODY, ... } // confidence-aware matching
```

## EXPRESSIONS

```
LITERAL                          // 42, 3.14, "text", true, false, [1,2,3]
IDENTIFIER                       // variable_name
EXPR.field                       // field access
EXPR[INDEX]                      // subscript — sugar for get(EXPR, INDEX)
FUNC(ARGS)                       // function/intent call
EXPR + EXPR                      // arithmetic: + - * / %
EXPR == EXPR                     // comparison: == != < > <= >=
EXPR and EXPR                    // logic: and or not
EXPR in [ITEMS]                  // membership
EXPR not in [ITEMS]              // negated membership
[EXPR, EXPR, ...]               // list literal
```

Operator precedence (high to low): unary(-,not) → */% → +- → comparison/in → and → or

## BUILT-IN FUNCTIONS

### Text
```
length(text: Text) -> Number
split(text: Text, delimiter: Text) -> [Text]
join(items: [Text], delimiter: Text) -> Text
trim(text: Text) -> Text
upper(text: Text) -> Text
lower(text: Text) -> Text
starts_with(text: Text, prefix: Text) -> Boolean
ends_with(text: Text, suffix: Text) -> Boolean
replace(text: Text, old: Text, new: Text) -> Text
slice(text: Text, start: Number, end: Number) -> Text
index_of(text: Text, sub: Text) -> Number      // first index, -1 if absent
```

### List
```
length(list: [T]) -> Number
get(list: [T], index: Number) -> T          // single element access
append(list: [T], item: T) -> [T]
sort(list: [T]) -> [T]
reverse(list: [T]) -> [T]
range(start: Number, end: Number) -> [Number]
map(list: [T], fn_name: Text) -> [T]
filter(list: [T], fn_name: Text) -> [T]
reduce(list: [T], fn_name: Text, initial: T) -> T
make_record(pairs: [[Text, Any]]) -> Record   // [["k", v], ...] → record
get(record: Record, key: Text) -> Any         // record field access (also works as obj.key)
is_null(value: Any) -> Boolean                // true iff value is the None sentinel
```

Note: map/filter/reduce take fn NAMES as strings, not lambda expressions.
Note: get() returns a single element of a list, OR a field of a record. Use slice() for sub-lists.
Note: `record.field` dot syntax also works on records (equivalent to `get(record, "field")`).
Note: undefined function calls now raise NameError loudly — no silent truthy fallback. If you need a missing-value check, use `is_null(value)` for None sentinels and `is_error(result)` for Result types.

### Conversion
```
to_number(text: Text) -> Number | None
to_text(value: Any) -> Text
to_boolean(value: Any) -> Boolean
```

### Math
```
abs(n: Number) -> Number
max(list: [Number]) -> Number
min(list: [Number]) -> Number
round(n: Number) -> Number                   // banker's rounding
round(n: Number, digits: Number) -> Number   // round to N decimal places
floor(n: Number) -> Number
ceil(n: Number) -> Number
sqrt(n: Number) -> Number | Result           // Result error on negative input
pow(base: Number, exp: Number) -> Number
```

### Result (error handling)
```
ok(value: Any) -> Result                     // wrap a success value
error(message: Text) -> Result               // wrap an error
is_ok(result: Result) -> Boolean             // true if ok
is_error(result: Result) -> Boolean          // true if error
unwrap(result: Result) -> Any                // extract value (errors return UNWRAP_ERROR with confidence 0.0)
unwrap_error(result: Result) -> Text         // extract error message
unwrap_or(result: Result, default: Any) -> Any  // value if ok, default if error
```

Note: to_number() returns a Result error on non-numeric input. Use is_error() to check before using the value.

### Provenance (every value knows where it came from)
```
origin_of(value: Any) -> Record              // {kind, name, model_id?, at?, parents?}
lineage_of(value: Any) -> [Record]           // flat post-order list of origin nodes
has_intent_origin(value: Any) -> Boolean     // true iff an intent is anywhere in the origin tree
has_effect_origin(value: Any) -> Boolean     // true iff a perform is anywhere in the origin tree
```

### Calibration (confidence that has been validated)
```
calibration_of(intent_name: Text) -> Record  // bucket stats for an intent
```

### Self-reflection (AIL programs that reason about AIL)
```
ail_parse_check(source: Text) -> Result[Text]   // ok(source) if valid, error(msg) if not
```
Pure — parses only, does not execute. Distinct from `eval_ail(source, input)`
which runs the inner program and is therefore impure. Use `ail_parse_check`
when you need to validate syntactic correctness of generated AIL without
firing any intents or effects it declares.

### HTML (reduce markup noise before sending to an intent)
```
strip_html(source: Text) -> Text            // visible text, tags gone
```
Pure. Returns only the visible text content of an HTML document — tags removed,
`<script>` and `<style>` bodies discarded, common entities decoded
(`&amp;` / `&lt;` / `&quot;` / `&#39;` / `&nbsp;`), whitespace collapsed.
Typical pattern: `text = strip_html(resp.body)` on an `http.get` response
before passing `text` to an intent for semantic extraction. Not a
sanitizer — output must not be re-embedded in HTML as-is; the purpose is
noise reduction for downstream LLM consumption.

### JSON (parse and emit structured data)
```
parse_json(source: Text) -> Result[Any]         // ok(value) on success, error(msg) on JSONDecodeError
encode_json(value: Any) -> Result[Text]         // ok(text) on success, error(msg) on non-encodable input
base64_encode(value: Text) -> Text              // base64-encode UTF-8 text; returns encoded Text directly (never fails)
base64_decode(value: Text) -> Result[Text]      // ok(text) on success, error(msg) if invalid base64 or non-UTF-8
crypto_verify_ed25519(public_key_hex: Text, signature_hex: Text, message: Text) -> Boolean
                                                // Ed25519 signature verification (requires cryptography>=41 package)
crypto_sign_ed25519(secret_key_hex: Text, message: Text) -> Result[Text]
                                                // ok(128-char-hex signature) on success; error on bad-length key
crypto_keygen_ed25519() -> Result[[Text, Text]]
                                                // ok([secret_key_hex, public_key_hex]) — both 64-char hex (32 bytes)
crypto_random_bytes(n: Number) -> Result[Text]
                                                // ok(2n-char hex) of cryptographically secure bytes; n in (0, 4096]
crypto_hash_password(plaintext: Text) -> Result[Text]
                                                // ok(PHC string: $argon2id$v=19$m=...,t=...,p=...$<salt>$<hash>).
                                                // Random salt per call; argon2id defaults (m=64MiB, t=3, p=1).
crypto_verify_password(plaintext: Text, phc: Text) -> Result[Boolean]
                                                // ok(true) on match, ok(false) on any mismatch including malformed PHC.
                                                // Constant-time comparison. Pattern-match a single Result shape.
```
All four are pure — no I/O, no LLM. `parse_json` returns a Record for JSON objects,
a List for arrays, Text / Number / Boolean primitives; use `get(value, key)`
after unwrapping. `encode_json` is the companion for building request bodies:
a list of two-element `[key, value]` pairs is emitted as a JSON object, any
other list as a JSON array, and primitives pass through. Escaping is the
runtime's job; authors must not hand-roll JSON via `join([...])`. `http.post_json`
calls `encode_json` internally — use it instead of `encode_json` + `http.post`
whenever you are talking to a JSON API.

`base64_encode` / `base64_decode` are required whenever an API spec says the field
must be base64-encoded — most commonly the GitHub Contents API (`content` field in
PUT /repos/.../contents/...) and any binary-over-JSON protocol.

Origin kinds: `"literal"`, `"input"`, `"fn"`, `"intent"`, `"builtin"`, `"attempt"`, `"effect"`.
Intent and effect origins additionally carry `at` (ISO-8601 timestamp).
Intent origins also carry `model_id`.

Rules:
- Literal values have kind `"literal"`.
- Entry parameters have kind `"input"` with `name` = parameter name.
- Each fn/intent/builtin call creates a new origin node; the parents are the
  origins of its arguments (literal parents are elided to keep trees small).
- Binary/unary/field/membership operations do NOT create new nodes — they
  inherit the first non-literal origin from their operands. This keeps
  origin trees bounded in tight loops.

These builtins cannot be shadowed by user-declared fns or intents.

## STDLIB MODULES

### stdlib/core
```
intent identity(x: Text) -> Text        // returns input unchanged
intent refuse(reason: Text) -> Text      // structured refusal
```

### stdlib/language
```
intent summarize(source: Text, max_tokens: Number) -> Text
intent translate(source: Text, target_language: Text) -> Text
intent classify(text: Text, labels: Text) -> Text
intent extract(source: Text, schema_description: Text) -> Text
intent rewrite(source: Text, instruction: Text) -> Text
intent critique(artifact: Text, rubric: Text) -> Text
```

### stdlib/utils
```
fn word_count(text: Text) -> Number
fn char_count(text: Text) -> Number
fn is_empty(text: Text) -> Boolean
fn repeat(text: Text, times: Number) -> Text
fn pad_left(text: Text, target_length: Number, pad_char: Text) -> Text
fn clamp(value: Number, lo: Number, hi: Number) -> Number
fn sum_list(numbers: [Number]) -> Number
fn average(numbers: [Number]) -> Number
fn flatten(nested: [[T]]) -> [T]
fn unique(items: [T]) -> [T]
fn take(items: [T], n: Number) -> [T]
fn zip_lists(a: [T], b: [U]) -> [[Any]]
fn contains(text: Text, sub: Text) -> Boolean
fn count_occurrences(text: Text, sub: Text) -> Number
fn truncate(text: Text, max: Number) -> Text      // clips + adds …
fn to_upper_first(text: Text) -> Text
fn plural_count(n: Number, singular: Text, plural: Text) -> Text
fn is_numeric(text: Text) -> Boolean
fn csv_to_rows(csv: Text) -> [[Text]]             // naive, no quoting
fn rows_to_csv(rows: [[Text]]) -> Text
```

## RESERVED KEYWORDS

```
intent context evolve effect entry import from as
goal constraints examples on_low_confidence trace
with override extends perform branch otherwise
prefer require when calibrate_on rollback_on
metric history keep_last under matching
and or not in such that
return true false threshold
fn pure if else for attempt try match confidence
```

## COMMENTS

```ail
// line comment
# also line comment (alias, accepted for Python-trained authors)
/* block comment */
```

## CONFIDENCE MODEL

- Every value is a pair: (value, confidence) where confidence ∈ [0, 1]
- Literals have confidence 1.0
- fn results have confidence 1.0
- intent results have model-reported confidence, **calibrated** if
  enough past observations exist
- Deterministic operations: confidence = min(input confidences)
- Access via: value.confidence (not yet exposed in MVP)

### Calibration loop

When the host program supplies a `metric_fn(intent, value, confidence)
-> (metric, rollback)`, every intent invocation also feeds the
calibrator: the (reported confidence, observed metric) pair is stored
in a bucket indexed by reported confidence (bucket width 0.1 by
default). Once a bucket accumulates `min_samples` observations (5 by
default), subsequent invocations whose reported confidence falls into
that bucket get their confidence REPLACED by the bucket's observed
mean — an empirically-grounded value.

Persistence: set `AIL_CALIBRATION_PATH` to a JSON path. The calibrator
loads at runtime init and saves on every observation. Multiple
processes converging on the same file accumulate a shared calibration
without coordinating.

Introspection from AIL: `calibration_of("intent_name")` returns a
record of `{bucket_range: {count, mean_observed, calibrated}}`, so a
program can say "if my classifier has no calibration data yet, route
around it" without special-casing.

The low-confidence handler (`on_low_confidence(threshold)` in intent
declarations) fires against the CALIBRATED value, not the reported
one. The reported number is what the model claimed; the calibrated
number is closer to truth, and that's the one users actually want to
gate on.

## IMPLICIT PARALLELISM

```ail
fn analyze(x: Text) -> Text {
    sentiments = classify_each(x)   // intent  }
    topics     = extract_topics(x)  // intent  } all three run concurrently
    summary    = summarize(x)       // intent  }
    return build_report(sentiments, topics, summary)
}
```

Consecutive Assignments whose RHS contain intent calls and are pairwise
independent are automatically grouped into parallel batches and issued
concurrently via a ThreadPoolExecutor. The author writes sequential
code; the runtime parallelizes the expensive (network-bound intent)
parts. No `async` keyword, no `await`, no Promise.all — the independence
is structural and the runtime uses it.

A batch is valid iff every statement is an Assignment, every RHS
contains at least one intent call, no two statements share an LHS, and
no RHS references another LHS in the batch. A batch of 1 degenerates to
serial execution. Dependent sequences fall through to serial.

Results are committed to scope in source order after all evaluations
complete, so determinism is preserved. Trace entries from a batch are
tagged with `parallel=True`.

## MATCH — CONFIDENCE-AWARE PATTERN DISPATCH

```ail
reply = match classify_sentiment(review) {
    "positive" with confidence > 0.9 => write_thank_you(review),
    "negative" with confidence > 0.9 => escalate_to_human(review),
    _ with confidence < 0.5          => ask_human_to_verify(review),
    "positive"                        => send_generic_happy(),
    "negative"                        => send_generic_sorry(),
    _                                 => send_generic_reply()
}
```

Each arm has shape `PATTERN [with confidence OP NUMBER] => BODY`.
Arms are tried in source order; the first whose pattern matches AND
whose optional confidence guard is satisfied has its body evaluated.

Patterns (v1):
  - Literal — exact equality (`"positive"`, `42`, `true`)
  - `_` — wildcard, matches anything
  - Any other identifier — variable binding; matches anything and
    exposes the subject's value in the arm body under that name

Confidence operators: `>`, `<`, `>=`, `<=`, `==`. The guard checks
the subject's confidence, not the pattern's.

Fallthrough: if no arm matches, the result is a Result-typed error.
Programs that want total coverage should end with a `_ =>` arm.

Why AIL has this: `match` and `branch` are complementary. `branch`
dispatches on arbitrary predicates (any truthy expression); `match`
dispatches on exact value with an optional belief gate. The confidence
guard is what no human language offers — because no human language
has confidence as a first-class runtime property.

Interactions with prior phases:
  - Purity: match is pure iff subject AND all arm patterns/bodies are
    pure. A pure fn containing `match intent_call() { ... }` is
    rejected at parse time.
  - Provenance: match does NOT introduce a new origin node; the
    selected arm body's origin is returned unchanged, so lineage
    queries see the underlying computation, not the dispatcher.
  - Parallelism: a match whose subject or any arm body contains an
    intent call is treated as "intent-bearing" for batching.
  - Attempt: `attempt { try match x { ... } }` is valid — match is
    an expression like any other.

## EFFECTS — INTERACTION WITH THE WORLD OUTSIDE THE INTERPRETER

```ail
content = perform file.read("/path/to/file")      // Text | Result-error
ok = perform file.write("/path/out", "contents")  // Result
resp = perform http.get("https://api.example.com/data")
resp = perform http.get("https://api.github.com/user", auth_headers)  // authenticated GET
  // resp is a Record: {status: Number, body: Text, ok: Boolean}
resp = perform http.post("https://api.example.com", "payload")
perform log("diagnostic message")                 // to stderr
```

Effects are side-effecting operations invoked via `perform EFFECT(args)`.
The effect name may be qualified (`http.get`, `file.read`) or bare
(`human_ask`, `log`). Every value produced by an effect carries an
`effect` origin node whose `name` is the fully-qualified effect name
and whose `at` is an ISO-8601 timestamp — you can audit exactly when
the side effect happened and what fed into it.

Built-in effects:
  - `http.get(url: Text, headers?: [[Text, Text]] | Record) -> Record`
    — `{status, body, ok}` on response. Optional headers as second
    positional arg or `headers:` kwarg: `perform http.get(url, auth)`.
    Required for any authenticated GET (GitHub /user, /repos, etc.).
  - `http.post(url: Text, body: Text, headers?: [[Text, Text]] | Record) -> Record`
  - `file.read(path: Text) -> Text | Result-error`
  - `file.write(path: Text, content: Text) -> Result`
  - `clock.now(format?: Text) -> Text` — ISO-8601 UTC by default
    (`"iso"`), or seconds-since-epoch when called with `"unix"`.
    Every returned value carries an effect-origin node.
  - `state.read(key: Text) -> Result[Any]` — read a previously
    stored value. error if the key is unset or invalid.
  - `state.write(key: Text, value: Any) -> Result[Boolean]` —
    atomic JSON write. value must serialize (Text/Number/Boolean/
    list of those is fine).
  - `state.has(key: Text) -> Boolean` — true if the key has a value.
  - `state.delete(key: Text) -> Result[Boolean]` — ok(true) if
    removed, ok(false) if not present.
  - `state.list_keys(prefix: Text) -> Result[[Text]]` — enumerate
    keys whose name begins with `prefix`, lex-asc sorted. Empty
    string lists every key. Snapshot semantics; concurrent writes
    after the call are not reflected. `err("invalid_prefix")` for
    a non-empty prefix that violates the key charset. Use a
    trailing `.` (e.g. `"delivered."`) to enumerate a namespace
    without including the namespace key itself.

    Keys are alphanumeric plus `_ - .`; anything else is rejected.
    State persists across requests inside an agentic project (under
    `.ail/state/keyval/`). Outside an agentic project the state
    effects return an explanatory error — set `AIL_STATE_DIR` to
    enable manual use from `ail run`.
  - `env.read(name: Text) -> Result[Text]` — read an OS environment
    variable. ok(value) when set (including empty string), error
    when unset or when name is empty. The only supported path for
    credentials (API keys, webhook URLs, auth tokens); hardcoding
    placeholders in source is forbidden by the authoring prompt.
  - `http.post(url: Text, body: Text, headers?: [[Text, Text]] |
    Record) -> Record` — optional headers kwarg for Bearer-auth
    APIs, content types, etc. Accepts either a list of
    [key, value] pairs (source-level, since AIL has no dict
    literal syntax) or a record (from intent / state). Example:
    `perform http.post(url, body, headers: [["Authorization", t],
    ["Content-Type", "application/json"]])`. **For JSON APIs use
    `http.post_json` instead** — the raw form is only for non-JSON
    payloads (form-encoded, plain text).
  - `http.post_json(url: Text, body: pair-list | Record,
    headers?: [[Text, Text]] | Record, timeout?: Number) -> Record`
    — POST with a structured body. Refuses a pre-formatted string
    body; the runtime serializes via `encode_json` and sets
    `Content-Type: application/json` (caller can override). The
    safe default for every JSON REST API that uses POST. `timeout`
    in seconds (default 30) — pass a small value (e.g. `timeout: 2`)
    for fan-out / best-effort calls so a slow endpoint can't block
    the publisher.
  - `http.put_json(url: Text, body: pair-list | Record,
    headers?: [[Text, Text]] | Record, timeout?: Number) -> Record`
    — identical to `http.post_json` but sends PUT. Required for APIs that use PUT
    for create/update — most notably GitHub Contents API
    (`PUT /repos/.../contents/...`). Using `http.post_json` on a
    PUT-only endpoint returns 404.
  - `http.graphql(url: Text, query: Text,
    variables?: pair-list | Record,
    headers?: [[Text, Text]] | Record) -> Result[Any]` — POST a
    GraphQL query and get back the `data` payload (or a clean
    error). The runtime collapses the full failure tree — HTTP
    4xx/5xx, unparseable JSON, non-empty `errors` array,
    `data` absent, `data: null` — into a single `Result`. On
    success returns `ok(data_record)` so the author can reach
    into mutation results with `get(get(..., "createDiscussion"),
    "discussion")` without ever touching the envelope. Exists
    because GraphQL's 200-with-errors convention made every
    hand-rolled error check a silent-failure vector in field
    test.
  - `schedule.every(seconds: Number) -> Result[Boolean]` — register
    a recurring tick. Two long-running contexts qualify: `ail up`
    (drives `entry main` periodically — pair with `state.write` so
    each tick stores a result) and `ail run` against a program with
    an `evolve` block (drives the `on_tick` lifecycle hook on the
    same cadence — call from `on_birth` / `on_genesis` to arm). Pair
    with `state.write` so each tick stores a result and GET / reads it.
    Seconds in (0, 86400]. Outside a long-running runtime the effect
    returns an explanatory error. Latest call wins.
  - `schedule.sleep(seconds: Number) -> Result[Boolean]` —
    cooperative wait. `ok(true)` once the duration elapses;
    `ok(false)` immediately for `0` or negative input (modeled as
    a no-op so `schedule.sleep(remaining)` is safe when
    `remaining` may compute to 0); `err("invalid duration")` for
    NaN/Inf; `err("interrupted")` when the process is shutting
    down. Use for long-poll / condition-wait composition (poll
    inbox + sleep + re-poll) and for in-tick throttling. Other
    workers in the same instance keep running.
  - `queue.push(msg: Record) -> Result[Text]` — enqueue a message
    onto the project's append-only queue (`<project>/.ail/queue.jsonl`).
    Returns the assigned `msg_id` (e.g. `"msg_0001"`). Any program in
    the project can push.
  - `queue.take() -> Result[Record]` — atomically pull the oldest
    pending message and mark it `working`. The returned record carries
    `_id` and `_retry_count` plus all original fields. Returns
    `error("empty")` when no pending messages.
  - `queue.done(msg_id: Text) -> Result[Text]` — mark a `working`
    message complete. Errors if the id isn't currently working.
  - `queue.retry(msg_id: Text, reason: Text) -> Result[Text]` —
    return a `working` message to `pending` with bumped retry count.
    Returns `"retried"` normally, `"dead_letter"` when the bump
    pushes the count to 5 (Physis: same threshold as scheduler
    self-throttle and evolve `consecutive_failures`). Dead-lettered
    messages are invisible to future `take` calls.
  - `human.approve(plan: Text, notify?: [Text]) -> Result[Record]` —
    **plan-validate-execute gate** with two channels (Arche #6, ergon
    2026-04-27). **Foreground**: writes `plan` to a pending-approval
    record that the agentic UI surfaces as an Approve / Decline card
    with a "의견 / comment" textarea. **Background** (when
    `STOA_BASE_URL` is set and `notify` recipients are available):
    also POSTs an approval letter to Stoa; the recipient(s) reply
    with `approve` (optionally followed by a comment) or
    `decline: <reason>`. The runtime polls both channels in parallel
    — first decision wins. `notify` defaults to
    `git config ail.identity` if unset. On Approve:
    `ok({approved: true, comment: Text})`. On Decline:
    `error("user declined: <reason>")`. Timeout via
    `AIL_APPROVE_TIMEOUT_S` env (default 600s).
    Call this BEFORE any irreversible side effect (`http.post_json`
    to a public channel, sending mail, creating issues/PRs/
    discussions, etc.). Read `get(unwrap(r), "comment")` to adapt
    to user feedback.
  - `ail.run(code: Text, input?: Text) -> Result[Text]` — **meta-programming
    gate**. Compiles and executes an AIL source string and returns the
    entry's result as Text. The sub-program runs in the same executor
    (same adapter, same `human.approve` gate, same purity constraints)
    so the HEAAL harness is never bypassed. Recursion depth ≥ 3 logs a
    warning; ≥ 8 returns a hard `Result-error`. Use with `intent` to
    create self-writing autonomous agents:
    `intent write_program(goal) -> Text` then
    `perform ail.run(program, input)`.
  - `search.web(query: Text, count?: Number) -> Result[List[Record]]` —
    web search with automatic backend fallback. Each result Record has
    `title`, `url`, `snippet` fields. Backend priority:
    (1) Google Custom Search API — set `GOOGLE_SEARCH_API_KEY` +
    `GOOGLE_SEARCH_CX` env vars; skipped if absent or quota exceeded.
    (2) SearXNG — set `SEARXNG_BASE_URL` env var; skipped if absent.
    (3) DuckDuckGo HTML — always tried; no key needed.
    Confidence reflects backend quality: Google 0.9, SearXNG 0.8,
    DuckDuckGo 0.7. Returns Result-error only when all backends fail.
  - `inherit_testament() -> Result[Testament]` — **Physis (v0.3)**.
    Read the testament written by the predecessor generation of this
    evolve block. Returns `error("no testament — genesis")` for the
    first generation (no predecessor). Returns `ok(testament)` for
    generation N+1, where `testament` is a Record with fields:
    `generation`, `predecessor_id`, `reason`, `observed_patterns`,
    `advice`, `params`, `born_at`, `died_at`, `lifetime_s`.
    Blocked inside `pure fn` (it is I/O). Call at entry startup:
    `t_r = perform inherit_testament(); if is_ok(t_r) { ... }`.
    The `error` case means genesis — handle it without treating it as
    a failure. Testament is written automatically when `rollback_on`
    fires and the program defines `pure fn on_death(reason, history)`.
  - `http.respond(status: Number, content_type: Text, body: Text)` —
    server response from inside an `evolve` server arm. Used with
    `evolve ... when request_received(req) { ... }` blocks.
  - `email.send(to: Text, subject: Text, body: Text) -> Result[Text]` —
    send an email via Gmail SMTP. Reads `GMAIL_USER` and
    `GMAIL_APP_PASSWORD` from environment. Returns `ok("sent")` on
    success, `error(...)` on failure. Use for outbound notifications to
    humans (e.g., replying to a Stoa message that carries `from_email`).
  - `db.execute(path: Text, sql: Text, params: [Any]?) -> Result[Number]` —
    run an INSERT/UPDATE/DELETE/CREATE on a SQLite file at `path`.
    `params` is an optional list of scalars bound to `?` placeholders.
    Returns `ok(rowcount)` or `error(...)`. WAL mode is enabled.
  - `db.query(path: Text, sql: Text, params: [Any]?) -> Result[[[Any]]]` —
    run a SELECT on a SQLite file. Returns `ok([[col1, col2, ...], ...])`
    — a list of rows where each row is a list of column values. Empty
    result is `ok([])`. Column names are not returned. Use for indexed
    reads (e.g., `since_id` polling) instead of loading a whole JSON blob.

    **Lifecycle doctrine (AIL #10):** each `db.execute` / `db.query` call
    opens a fresh `sqlite3` connection and closes it in a `finally`
    block. There is no module-level pool. This is safe under load and
    leaks no Python objects — but it does pay open / `PRAGMA journal_mode
    =WAL` / close cost on every call. In a long-running runtime (`ail up`
    or `ail run` with `evolve`), the *caller* owns hot-path discipline:
    don't re-run schema bootstraps inside per-request handlers; guard
    repeat `db.execute("CREATE TABLE IF NOT EXISTS ...")` with a once-per-
    process flag in `state.*` or a module-level cache; budget your
    request handler's DB calls the way you'd budget HTTP calls.
  - `git.commit(repo_path: Text, message: Text, paths: [Text]?) -> Result[Text]` —
    stage `paths` (or all changes if `None`) in the repo and commit.
    Returns `ok(commit_sha)` or `error(stderr)`. Auth + user.name come
    from ambient git config (the agent's own identity).
  - `git.push(repo_path: Text, remote?: Text, branch?: Text) -> Result[Text]` —
    push `branch` (or current HEAD) to `remote` (default `"origin"`).
    Returns `ok(stdout)` or `error(stderr)`.
  - `git.pull(repo_path: Text, remote?: Text, branch?: Text) -> Result[Text]` —
    pull from `remote` into the current branch. Returns `ok(stdout)`
    or `error(stderr)`. Merge conflicts are surfaced as errors —
    callers decide retry / abort / `human.approve`.
  - `gh.pr_list(repo?: Text, state?: Text, limit?: Number) -> Result[[Record]]` —
    list pull requests via `gh` CLI. Each record:
    `number, title, state, headRefName, baseRefName, url, author`.
    `state` defaults to `"open"`. Errors when `gh` is missing or unauthed.
  - `gh.pr_view(number: Number, repo?: Text) -> Result[Record]` —
    view one PR. Record adds `body` to the pr_list shape.
  - `gh.pr_create(title: Text, body: Text, repo?: Text, base?: Text, head?: Text, draft?: Boolean) -> Result[Text]` —
    create a PR from `head` into `base`. Returns the PR URL.
  - `gh.issue_list(repo?: Text, state?: Text, limit?: Number) -> Result[[Record]]` —
    list issues. Each record: `number, title, state, url, author, labels` (`[Text]`).
    `gh.*` exists as a named namespace (not generic `process.spawn`)
    so the ledger keeps "gh.pr_create happened", not "shell happened".
    For new tools, add a new named effect — do not reach for shell.
  - `mneme.save(message?: Text, repo_path?: Text) -> Result[Text]` —
    stage `Identity.md` / `Bonds.md` / `Will.md` (whichever exist) in
    the repo, commit with `message`, push to upstream. Returns the
    commit sha. Errors when not a git repo, no identity files, or
    nothing changed since last save. `repo_path` defaults to cwd.
    Idiomatic in `on_dying` so the next generation inherits.
  - `mneme.load(repo_path?: Text) -> Result[Record]` —
    `git pull --ff-only` (skipped silently if no remote) and read the
    three identity files. Record: `identity, bonds, will, pull_warning`
    (each Text or None). Idiomatic in `on_birth`.
  - `mneme.log(limit?: Number, repo_path?: Text) -> Result[[Record]]` —
    `git log` over the identity files only (so unrelated commits don't
    dominate). Each record: `sha, author, date (ISO), message`.
  - `secrets.get(key: Text) -> Result[Text]` — read a secret from
    `~/.ail/.env` (hot layer) or `os.environ`. Returns `ok(value)` or
    `error(...)` when not found. Use instead of `env.read` for
    credentials that should survive session restarts.
  - `secrets.set(key: Text, value: Text) -> Result[Text]` — write a
    secret to `~/.ail/.env` and `os.environ`. Returns `ok("secret
    '<key>' stored")`. Persists across process restarts.
  - `secrets.list() -> Result[[Text]]` — return the list of key names
    stored in `~/.ail/.env`. Values are never included.
  - `secrets.revoke(key: Text) -> Result[Text]` — overwrite a secret's
    value with `""` without removing the key. The key name remains as
    an audit record. Use instead of deletion ("deletion is movement").
  - `budget.charge(category: Text, amount: Number) -> Result[Number]` —
    atomic per-identity consume against a configured ceiling. Returns
    `ok(remaining)` on success. If the charge would exceed the
    ceiling, returns `Result-error("budget_exceeded:<cat> c+a>ceil")`
    AND does NOT update `consumed` — the agent can pattern-match and
    slow down, ask, or stop. Unknown identity/category returns
    `Result-error("budget_unconfigured:<id>/<cat>")` so a missing
    config surfaces instead of running uncapped. Identity = `STOA_NAME`
    or `agents/<name>/` dir; missing both → "anonymous" with fixed
    defaults (llm_tokens=100, compute_minutes=1, stoa_push=5).
  - `budget.remaining(category: Text) -> Result[Number]` — read-only
    `ok(ceiling - consumed)`. Same `budget_unconfigured` failure as
    charge.
  - `budget.reset(category: Text) -> Result[Number]` — zero `consumed`,
    return `ok(ceiling)`. The ceiling is unchanged. Wall-clock
    auto-rollover is intentionally absent — period boundaries are
    explicit agent decisions so they appear in the ledger.
  - `diag.gc_count() -> Result[[Number]]` — CPython GC generation
    counts `[gen0, gen1, gen2]`. Read-only.
  - `diag.object_count() -> Result[Number]` — `len(gc.get_objects())`,
    total tracked objects. Read-only.
  - `diag.thread_count() -> Result[Number]` —
    `threading.active_count()`. Read-only.
  - `diag.tracemalloc_start(frames: Number) -> Result[Boolean]` —
    start the Python tracemalloc tracer with `frames` traceback
    depth. Idempotent: a second call while already tracing is a
    no-op success.
  - `diag.tracemalloc_stop() -> Result[Boolean]` — stop the tracer.
    Idempotent: calling when not tracing is a no-op success.
  - `diag.tracemalloc_snapshot(top_n: Number) -> Result[[Record]]` —
    top-N statistics grouped by `lineno`. Each row:
    `{ file: Text, line: Number, size_kb: Number, count: Number }`.
    Returns `Result-error("tracemalloc_not_started")` if `start`
    was never called — silent empty rows would hide that gap.
  - `image.embed(src: Text, alt?: Text) -> Text` — return a markdown
    image string (`![alt](url)`) the chat / run UI renders inline.
    For local file paths the bytes are base64-encoded into a
    `data:image/...` URL so the UI does not need filesystem access;
    `http(s)://` and `data:` URLs pass through. Use it to surface
    plots, screenshots, or any rendered output to the user — the
    return value is plain Text, so feed it to `perform log(...)` or
    return it from an entry, anywhere markdown rendering applies.
    Returns Result-error if a local file is missing or unreadable.
  - `log(message: Any)` — stderr, returns nothing
  - `human_ask(question: Text) -> Text`

Interactions with prior phases:
  - `pure fn` rejects any body containing `perform`. A pure fn cannot
    invoke an effect, directly or transitively.
  - Implicit parallelism does NOT batch effect-containing assignments.
    `perform` calls run in source order so their observable side effects
    are deterministic.
  - `attempt` blocks CAN contain `perform` tries, enabling fallback
    patterns like "try a cheap local file, else fetch from the network".

## ATTEMPT — CONFIDENCE-PRIORITY CASCADE

```ail
result = attempt {
    try fast_method(x)       // try first; if qualifies, stop
    try slower_method(x)     // otherwise this
    try expensive_fallback(x) // last resort
}
```

A try *qualifies* when its result is NOT a Result-typed `error(...)`
AND its confidence is at least 0.7 (the default threshold). The first
qualifying try's value is returned; if none qualify, the last try's
value is returned (with its low confidence preserved, so the caller
can detect fallthrough).

The returned value carries an `attempt` origin node whose `name` field
is the index (as a string) of the try that was selected. Upstream
lineage is preserved through the origin's `parents` field.

Unique to AIL: confidence-aware fallback cascade is first-class control
flow. `branch` expresses explicit probabilistic dispatch; `attempt`
expresses "try cheap first, fall back to expensive if unconfident."

## PROVENANCE MODEL

Every value also carries an `origin` — a runtime record of how it was
produced. Unlike confidence (one number), origin is a tree linking a value
to the origins of the inputs that fed into it. Use the builtins
`origin_of`, `lineage_of`, `has_intent_origin` to query it from AIL code.

This is unique to AIL — no human language tracks value lineage at runtime.
It exists because AI-authored code often mixes deterministic computation
with LLM calls, and the author (an AI) must be able to ask "was a model
involved in producing this number?" without manually threading it through.

## GRAMMAR LIMITATIONS (KNOWN)

1. `goal:` field does not accept commas in its value (commas are list separators)
2. Reserved keywords (`with`, `in`, `for`, etc.) cannot appear in goal prose
3. `while` does not exist (by design — see spec/07 §3.3)
4. No lambda expressions; use named fn + pass name as string to map/filter/reduce
5. Types are runtime-checked, not compile-time checked

## COMPLETE EXAMPLES WITH INPUT/OUTPUT

### Example 1: Pure computation (no LLM)

```ail
fn factorial(n: Number) -> Number {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}

entry main(x: Text) {
    return factorial(6)
}
```

INPUT: any
OUTPUT: 720
CONFIDENCE: 1.0
LLM_CALLS: 0

### Example 2: FizzBuzz

```ail
fn fizzbuzz(n: Number) -> Text {
    if n % 15 == 0 { return "FizzBuzz" }
    if n % 3 == 0 { return "Fizz" }
    if n % 5 == 0 { return "Buzz" }
    return to_text(n)
}

fn fizzbuzz_range(limit: Number) -> Text {
    results = []
    for i in range(1, limit + 1) {
        results = append(results, fizzbuzz(i))
    }
    return join(results, ", ")
}

entry main(limit: Text) {
    return fizzbuzz_range(to_number(limit))
}
```

INPUT: "15"
OUTPUT: "1, 2, Fizz, 4, Buzz, Fizz, 7, 8, Fizz, Buzz, 11, Fizz, 13, 14, FizzBuzz"
CONFIDENCE: 1.0
LLM_CALLS: 0

### Example 3: Hybrid fn + intent

```ail
import classify from "stdlib/language"

fn word_count(text: Text) -> Number {
    return length(split(text, " "))
}

fn build_report(label: Text, count: Number) -> Text {
    return join([label, " (", to_text(count), " words)"], "")
}

entry main(text: Text) {
    sentiment = classify(text, "positive_negative_neutral")
    count = word_count(text)
    return build_report(sentiment, count)
}
```

INPUT: "I love this product so much"
OUTPUT: "positive (6 words)" (approximate — LLM output varies)
CONFIDENCE: ~0.85 (from model)
LLM_CALLS: 1

### Example 4: Context inheritance

```ail
context translation_job extends default {
    preserve: [formatting, proper_nouns]
}

context formal_korean extends translation_job {
    override register: "formal"
    target_language: "Korean"
}

intent translate_document(source: Text) -> Text {
    goal: Text faithfully translating source into context.target_language
}

entry main(document: Text) {
    with context formal_korean:
        translated = translate_document(document)
    return translated
}
```

INPUT: "Hello, how are you?"
OUTPUT: (Korean formal translation — LLM output varies)
CONFIDENCE: ~0.85
LLM_CALLS: 1
CONTEXT_CHAIN: default → translation_job → formal_korean

### Example 5: Evolution

```ail
intent classify(x: Text) -> Text { goal: label }

evolve classify {
    metric: score(sampled: 1.0)
    when score < 0.7 {
        retune confidence_threshold: within [0.5, 0.95]
    }
    rollback_on: score < 0.3
    history: keep_last 10
}

entry main(x: Text) { return classify(x) }
```

BEHAVIOR:
- If metric average stays above 0.7: no evolution, v0 persists
- If metric average drops below 0.7 after 10+ samples: retune fires, v1 applied with threshold = midpoint(0.5, 0.95) = 0.725
- If metric drops below 0.3 after version change: rollback to prior version

## HOW TO RUN

```bash
cd reference-impl
pip install -e ".[anthropic]"

# Without LLM (fn-only programs, or mock for intent programs):
ail run PROGRAM.ail --input "INPUT" --mock

# With Anthropic:
export ANTHROPIC_API_KEY=sk-ant-...
ail run PROGRAM.ail --input "INPUT"

# With local Ollama (no API key; requires `ollama serve` + a pulled model):
export AIL_OLLAMA_MODEL=llama3.1:latest
ail run PROGRAM.ail --input "INPUT"

# Programmatically:
from ail import run
result, trace = run("program.ail", input="hello")
# result.value, result.confidence

# Explicit adapter selection:
from ail.runtime.ollama_adapter import OllamaAdapter
result, trace = run("program.ail", input="hi",
                    adapter=OllamaAdapter(model="gemma2:latest"))
```

## PYTHON API

```python
from ail import run, compile_source, MockAdapter

# Run with mock (no API key):
result, trace = run(source_or_path, input="text", adapter=MockAdapter())

# Run with real model:
result, trace = run(source_or_path, input="text")

# With evolution feedback:
def metric_fn(intent_name, value, confidence):
    return (feedback_score, rollback_signal)
result, trace = run(source, input="text", metric_fn=metric_fn)

# Parse only:
program = compile_source(ail_source_text)
```
