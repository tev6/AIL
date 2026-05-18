# RFC — Pure-AIL autonomous agent demo

**Author:** Telos · **Cycle:** 13 · **Status:** draft
**Doctrine tie:** AIL#23 §0 ("no human spawns a fresh session")
**Companion:** Tekton charter.ail reimplementation (Tekton lane)

## 0. Motivation

박상현 framing (cycle 13):

> "완전 자율 에이전트 = AIL 프로그램이 호스트 머신에서 evolve 서버로
> 살면서, LLM은 intent로 직접 부르고, Stoa 통신·자원 인지·자기
> 수정까지 *전부 AIL 안에서* 한다. Claude Code 위 CAST는 임시
> rehearsal — 진짜 자취는 AIL 프로그램 자체."

This RFC defines the smallest land that demonstrates "pure-AIL
autonomous agent." Today's Tekton pilot has a Python sidecar
(`outbox_dispatch.py`) for Stoa transport. The sidecar's three
duties — canonicalize, sign, POST — are now expressible *entirely
in AIL* because the underlying primitives are all shipped:

| sidecar duty | AIL primitive | Status |
|---|---|---|
| canonical bytes (RFC-001 §6.1) | pure fn `canonical_letter` | not yet authored |
| ed25519 sign | builtin `crypto_sign_ed25519` | shipped 1.71 |
| HTTP POST | effect `perform http.post` / `http.post_json` | shipped 1.10 |
| key load | effect `perform file.read` | shipped 1.0 |
| nonce | builtin `crypto_random_bytes(16)` | shipped 1.71 |
| timestamp | effect `perform clock.now` (formatter via stdlib) | shipped 1.0 |

**Net new effects: 0. Grammar changes: 0.** The demo is *composition
only*. That is the doctrine signal — the language is now expressive
enough that an autonomous agent is an AIL program, not a Python
program wrapping AIL.

## 1. Surface — `agents/tekton/stoa_send.ail`

A standalone, importable AIL module Tekton (and future CAST agents)
import.

```ail
// agents/tekton/stoa_send.ail
//
// Pure-AIL Stoa transport. Mirrors community-tools/stoa-cli/stoa_cli.py
// canonical_letter byte-for-byte (RFC-001 §6.1). No Python sidecar.

// --- canonical (pure fn, no effects) ---

pure fn esc(s: Text) -> Text {
    // RFC-001 §6.1 escape, fixed order:
    //   \\   →  \\\\
    //   |    →  \|
    //   ;    →  \;
    //   :    →  \:
    a = replace(s, "\\", "\\\\")
    b = replace(a, "|", "\\|")
    c = replace(b, ";", "\\;")
    return replace(c, ":", "\\:")
}

pure fn one_recipient_canon(r: Record) -> Text {
    return esc(get(r, "name")) + ":" + esc(get(r, "address"))
}

pure fn join_to(sorted_to: [Record]) -> Text {
    // Each entry: { name, address }. Caller sorts by name.
    // `map` takes a fn *name* (Text), not an inline closure — AIL
    // idiom for higher-order is named helpers, not lambdas.
    parts = map(sorted_to, "one_recipient_canon")
    return join(parts, ";")
}

pure fn canonical_letter(
    from_name: Text, from_address: Text,
    sorted_to: [Record],
    content: Text, created_at: Text, nonce: Text
) -> Text {
    return join([
        "letter",
        esc(from_name),
        esc(from_address),
        join_to(sorted_to),
        esc(content),
        esc(created_at),
        esc(nonce),
    ], "|")
}

// --- key + timestamp ---

fn load_secret_key_hex(identity: Text) -> Result[Text] {
    // Read ~/.ail/keys/<identity>.key. The file holds a 64-char hex
    // string (32-byte ed25519 secret). 0600-mode file convention.
    home = unwrap_or(perform env.read("HOME"), "")
    path = home + "/.ail/keys/" + identity + ".key"
    r = perform file.read(path)
    if is_error(r) { return r }
    return ok(trim(unwrap(r)))
}

fn iso8601_utc() -> Text {
    // clock.now() already returns the canonical "YYYY-MM-DDTHH:MM:SSZ"
    // string by default (clock.py:_clock_now). No formatting needed.
    return perform clock.now()
}

// --- send (signed POST) ---

fn send(
    identity: Text,
    recipient_name: Text,
    recipient_address: Text,
    content: Text
) -> Result[Record] {
    sk_r = load_secret_key_hex(identity)
    if is_error(sk_r) { return sk_r }
    sk_hex = unwrap(sk_r)

    nonce_r = crypto_random_bytes(16)
    if is_error(nonce_r) { return nonce_r }
    nonce = unwrap(nonce_r)

    ts_r = iso8601_utc()
    if is_error(ts_r) { return ts_r }
    created_at = unwrap(ts_r)

    from_addr = "https://ail-stoa.up.railway.app/inbox/" + identity
    to_list = [
        { name: recipient_name, address: recipient_address }
    ]
    canon = canonical_letter(
        identity, from_addr,
        to_list,
        content, created_at, nonce,
    )

    sig_r = crypto_sign_ed25519(sk_hex, canon)
    if is_error(sig_r) { return sig_r }
    signature = unwrap(sig_r)

    envelope = {
        "from": { "name": identity, "address": from_addr },
        "to":   to_list,
        "content": content,
        "created_at": created_at,
        "nonce": nonce,
        "signature": signature,
    }
    return perform http.post_json(
        "https://ail-stoa.up.railway.app/api/v1/messages",
        envelope, [],
    )
}
```

The module is pure ed25519 transport. Recipient list is single for
the first land — multi-recipient is a follow-up (sort, then build
the canonical to_str the same way).

## 2. Tekton charter integration

Tekton's `agents/tekton/charter.ail` keeps its decision shape; the
only change is the outbox edge.

**Before (today):**
```
write letter JSON to .ail/outbox/*.json
  → outbox_dispatch.py polls .ail/outbox/
    → reads file, builds envelope, signs, POSTs
```

**After (this RFC):**
```
import stoa_send from "./stoa_send"

// inside charter on drop detected:
intent explain_drop(prev: Number, now: Number) -> Text {
    goal: "One sentence: most likely cause of the bench drop from
           {prev}% to {now}%. Be specific about which test category."
}
hypothesis = explain_drop(70, score)

body = build_body(score, hypothesis, ...)
stoa_send.send(
    "tekton",
    "hyun06000",
    "https://ail-stoa.up.railway.app/inbox/hyun06000",
    body,
)
```

The `intent` call is the new piece — Tekton today writes the alert
body via plain string concat, which means the "agent" has no
*language* yet, only behavior. Folding one `intent` makes the
alert *say something* rather than dump numbers. That is also the
first place an `evolve rollback_on` block can guard against a bad
hypothesis (cf. §3).

`outbox_dispatch.py` is retired after this lands. The poll loop,
file-based outbox, sidecar-process supervision — all gone. The
agent's transport is the same `perform http.post_json` call any
ordinary AIL program would make.

## 3. Self-modification (`evolve rollback_on`)

AIL#23 §4 acceptance bullet 4: "≥ 1 self-modification with
rollback_on." A natural fit on top of §2:

```ail
evolve hypothesis_quality rollback_on {
    // After N drop alerts, look at how many led to a real cause
    // identification (human confirmed via inbox reply). If the
    // hypothesis quality is below threshold, roll back to a
    // simpler "raw numbers only" body builder.
} when on_period_close {
    quality = read_hypothesis_feedback_score()
    if quality < 0.5 {
        return rollback_to("plain_numbers_body")
    }
    return keep_current()
}
```

This is the minimum shape. The actual mutation strategy is Tekton's
to design — RFC doesn't fix it, only declares the bullet is
reachable now that the agent's language layer (`intent`) exists.

## 4. AIL#23 §4 acceptance — status after this RFC lands

| bullet | status |
|---|---|
| 1. ≥ 7 days continuous run | unblocked (Phase B Hestia migration, separate resource ask) |
| 2. identity + memory across the run | wired (state.* + Mneme handoff once §5 vault deploys) |
| 3. ≥ N self-decided next actions per day | wired (charter charge per tick) |
| 4. ≥ 1 self-modification + rollback_on | wired by §3 of this RFC |
| 5. coordinates ≥ 1 other autonomous agent via Stoa | **wired by §1+§2 of this RFC** — pure-AIL Stoa transport closes the last sidecar dependency |
| 6. stays inside declared budget | wired (G5 Phase 0 land, v1.74.0) |
| 7. Go + Rust runtime conformance | future (G4 Tekton lane) |

So six of seven bullets are wired when this RFC's pieces land. The
seventh is multi-runtime parity — a separate, larger effort. The
demo "AIL is expressive enough for an autonomous agent" claim
stands on bullets 1–6.

## 5. Implementation phases

- **Phase 0 (this RFC)** — `agents/tekton/stoa_send.ail` exists,
  canonical_letter has a byte-for-byte test against the Python
  sidecar's output for the same envelope. Charter integration is
  Tekton's lane, separate PR.
- **Phase 1 (Tekton)** — charter.ail imports stoa_send, retires
  `outbox_dispatch.py`. One `intent explain_drop` fold. Mac local
  run verifies a signed envelope round-trip via the pure-AIL path.
- **Phase 2 (Tekton)** — `evolve hypothesis_quality` block. Local
  run.
- **Phase 3 (박상현 resource)** — Hestia migration. 7+ day run.
  AIL#23 §4 bullets 1–6 verified by ledger trace.

## 6. Risks and limitations

- **Verified-present builtins:** `replace`, `map` (takes fn *name*
  as Text), `trim`, `join`, `length`, `slice`, `to_text`,
  `to_number`, `range`, `sort` (plain comparator). All in the
  reference card.
- **Time format — no gap.** First-pass risk audit assumed
  `clock.now` returned epoch seconds. It does not — `clock.now()`
  returns `"YYYY-MM-DDTHH:MM:SSZ"` by default (see
  `reference-impl/ail/runtime/executor_effects/clock.py`). The
  `iso8601_utc` helper in §1 collapses to a single `perform
  clock.now()`. No builtin needed.
- **One real gap — `sort_by` for multi-recipient.**
  `sort_by(list: [Record], key_fn_name: Text) -> [Record]` does
  not exist. Plain `sort` of records is undefined. For Phase 0 of
  this RFC, `to_list` is single-recipient, so the canonical builds
  a 1-element list with no sort needed. The gap matters when CAST
  letters address multiple recipients; lands as a `stdlib/list`
  patch alongside Phase 1.
- **PEM vs hex.** stoa-cli uses raw hex for the secret key. This
  RFC keeps that format. If/when AIL identities switch to PEM
  (Mneme vault decision), `load_secret_key_hex` adds a parse step.
- **HTTP error handling.** `http.post_json` returns `ok(response)`
  even on 4xx/5xx — the agent must inspect status. Standard AIL
  pattern, not a blocker but worth a sentence in charter docs.
- **Side-channel: Phase 0 of stoa-cli stays in repo** as a
  test-tooling reference until Phase 3 lands. After that, the
  sidecar can move to a deprecated/ folder or be removed.

## 7. Why this is the right next step

Three reasons:

1. **No new effects, no grammar changes.** The land surface is
   compositional. Every primitive used has its own test coverage
   already. This means the "first pure-AIL agent" story does not
   require waiting for any other gap to close.
2. **The intent fold is the first time the agent has language.**
   Until now Tekton's alert is a static template. After §2, the
   model can say *why*. That is the smallest possible expression
   of "agent" beyond "scheduler."
3. **Symmetric closure with the G3 (Stoa coordinate) and G5
   (budget) work already shipped.** G3 made signed letters
   possible; G5 made resource-aware action possible; this RFC
   moves the signing and the resource-aware loop into the AIL
   program itself. The story closes on its own.

## 8. Cross-references

- AIL#23 §0 + §4 (north-star)
- `docs/proposals/effect-conformance.md` (D7 — substrate tier)
- `docs/proposals/builtins-canonical.md` (D8 — builtin surface)
- `docs/proposals/budget.md` (G5 — resource autonomy, just landed)
- `community-tools/stoa-cli/stoa_cli.py:canonical_letter`
  (the function this RFC mirrors in AIL)
- `agents/tekton/charter.ail` (the consumer)
- `agents/tekton/outbox_dispatch.py` (the artifact this RFC retires)

— Telos, 사이클 13
