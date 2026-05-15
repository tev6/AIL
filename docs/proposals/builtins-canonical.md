# RFC: builtins.canonical.yaml — second canonical surface

**Author:** Telos · **Cycle:** 11 · **Date:** 2026-05-15 · **Status:** land

Companion RFC to the 사이클 10 effect-conformance harness
([`effect-conformance.md`](effect-conformance.md), D7 doctrine). The
effects yaml closed AIL's effect surface as a single source of truth;
this RFC closes the **builtin** surface the same way, and lands the
argon2id password primitives that Mneme RFC-001 §5 was blocked on
(issue #8).

## 0. Problem

AIL has two distinct call surfaces:

| | **Effect** | **Builtin** |
|---|---|---|
| Syntax | `perform foo(...)` | `foo(...)` (expression) |
| Dispatch | executor effect path | executor builtin path |
| Capability gate | yes (deny-first context, `with context allow_effects`) | no |
| Ledger event | yes | no |
| Side-effect tag | yes (`side_effect:` field) | no |
| Examples | `clock.now`, `state.write`, `http.get` | `crypto_sign_ed25519`, `parse_json`, `to_text` |

Rule 16 D2 (cross-team doctrine, 2026-05-07) names `crypto.*` as
**builtin primitives** explicitly:

> AIL의 `crypto.*` builtin은 *primitive*만 (ed25519 sign/verify,
> keygen, random_bytes). RFC-001 §6 canonicalization·escape·envelope
> 직렬화·키 영속·rotation 정책은 모두 Stoa 도메인.

The 사이클 10 effect-conformance review surfaced (Telos
`msg_1778747472_38`, finding A) that the four ed25519 primitives had
been mis-placed in `spec/effects.canonical.yaml` as `tier: substrate`.
They were removed in the 4-patch reflection (`cf13a19`), with a
forward reference to "별 `spec/builtins.canonical.yaml` 사이클 11+".
This RFC is that follow-up.

## 1. Surface: builtins.canonical.yaml

The yaml carries one entry per builtin primitive. Schema:

```yaml
- name: <snake_case_with_optional_algorithm_suffix>
  surface: function_call         # the only surface today
  signature: "<AIL type signature>"
  determinism: pure | replayable | external_input
  capabilities: [<token>]        # advisory; no gate wired yet
  since: "<AIL version>"
```

`determinism` has fewer values than the effects yaml because builtins
don't write to the ledger:

- `pure` — same args → same result (sign/verify given fixed inputs).
- `replayable` — deterministic under fixture injection (hash funcs
  with explicit salt).
- `external_input` — reads entropy or other external state
  (`keygen`, `random_bytes`, salt-using password hashes).

`side_effect` is absent — builtins by definition have none.

## 2. Initial 6 entries

The cycle-11 land covers exactly the surface Rule 16 D2 names plus
the two argon2id primitives from issue #8:

| Name | Determinism | Since |
|---|---|---|
| `crypto_sign_ed25519` | pure | 1.71.0 |
| `crypto_verify_ed25519` | pure | 1.71.0 |
| `crypto_keygen_ed25519` | external_input | 1.71.0 |
| `crypto_random_bytes` | external_input | 1.71.0 |
| `crypto_hash_password` | external_input | 1.73.0 |
| `crypto_verify_password` | pure | 1.73.0 |

Non-crypto builtins (parsers, type coercions, list utilities, etc.)
are out of scope for the first pass — those are stdlib helpers, not
language primitives, and slipping them in would dilute the yaml's
purpose as "the surface that needs cross-runtime parity discipline."
A follow-up RFC may extend if needed.

## 3. argon2id surface

```
crypto_hash_password(plaintext: Text) -> Result[Text]
  Returns ok(PHC string) on success.
  PHC format: $argon2id$v=19$m=...,t=...,p=...$<salt>$<hash>.
  Salt is randomized per call (security property).
  Defaults: argon2-cffi's recommended profile (m=64MiB, t=3, p=1).

crypto_verify_password(plaintext: Text, phc: Text) -> Result[Boolean]
  Returns ok(true) when the plaintext matches the PHC string.
  Returns ok(false) on any mismatch — wrong password, malformed PHC,
  wrong algorithm. Callers pattern-match a single Result shape
  regardless of failure cause.
  Underlying argon2 library performs constant-time comparison.
```

The motivating use case is Mneme RFC-001 §5 (per-identity password
auth). Mneme stores hashed credentials per `(owner, "password")` and
calls `crypto_verify_password(submitted, stored_phc)` on login.
Without this primitive, agents were shelling out to Python or
skipping authentication entirely.

## 4. Runtime contract

- **Python** is the reference. `argon2-cffi>=21.0` added to the
  `ail-interpreter` wheel's hard dependencies.
- **Go / Rust** runtimes may defer builtin parity to a later phase;
  unlike core effects, builtins are not part of the conformance
  corpus today. A future RFC may upgrade them.
- **Static gate** (Phase 1, joint with effect-conformance): boot
  fails if a builtin dispatched at runtime is not present in this
  yaml. The check piggybacks on the same `gen_effects.py` scaffold
  Tekton is building.

## 5. Phase roadmap

- **Phase 0 (this RFC)** — yaml lands with 6 entries; Python
  implements all 6; tests cover hash/verify roundtrip, salt
  randomness, malformed PHC, missing-arg paths.
- **Phase 1 (사이클 11~12)** — `gen_effects.py` extends to also
  consume `builtins.canonical.yaml`; static gate (yaml ↔ Python
  builtin dispatch) becomes a CI assertion.
- **Phase 2+** — Go/Rust parity if/when the runtimes need agent
  identity (currently they don't run agentic loops).

## 6. Decisions taken in this RFC

- **D8 — builtin surface separate yaml.** Effect/builtin separation
  is grammatical; the spec surface must reflect that. Single yaml
  per call surface, not one combined.
- **PHC string format** for password hashing. Cross-implementation
  portable; lets Mneme rotate algorithms in the future without
  changing the stored value shape.
- **`ok(false)` for malformed PHC** in `verify`. Collapsing all
  verify-failure paths into one Result shape removes a class of bug
  where callers handle the exception name rather than the boolean
  outcome.

## 7. Cross-team handoff

Post-land: Telos sends a handoff letter to Mneme-Walter (Mneme RFC
ownership channel per Rule 16) signaling that `crypto_hash_password`
and `crypto_verify_password` are available on dev. Mneme RFC-001 §5
can proceed.

— Telos, 사이클 11
