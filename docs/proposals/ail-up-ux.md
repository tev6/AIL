# RFC — `ail up` zero-config UX for autonomous agents

**Author:** Telos · **Cycle:** 13 · **Status:** draft
**Driver:** 박상현 framing (`msg_1779090522_52`):
> "나는 완전 자율 에이전트를 `ail up ..` 커멘드로 올릴 수 있었으면
> 좋겠어. 어떤 사용자라도 아주 쉽게 말이야"

## 0. Motivation

The pure-AIL agent capability landed in cycle 13 (Phases 0–2 of
`docs/proposals/pure-ail-agent-demo.md`). A working agent today
demands six pieces of manual setup before `ail up` will start it:

1. ed25519 keypair under `~/.ail/keys/<name>.{key,pub}`
2. Stoa-side public-key registration (`/api/v1/agents/<name>`)
3. `ANTHROPIC_API_KEY` (or equivalent) for `intent` calls
4. `AIL_BUDGET_CONFIG` pointing at a YAML for ceilings
5. `STOA_NAME` env var so the identity resolves
6. `AIL_STATE_DIR` writable for ledger / state.* / outbox

Today every one of these is "set the env, find the file, generate
the key first." A first-time user has to know all six exist. The
land below collapses that to a single `ail up agents/<name>`.

The capability is already there — this RFC is only about UX.

## 1. Scope (4 pieces)

### A. Smart path resolution + env auto-derive (Phase 0)

`ail up <path>` accepts both file and directory.

- **directory**: search for `charter.ail`, `main.ail`, `agent.ail`
  in that order. First hit is the entry. Multiple hits = error
  asking the user to pick.
- **file**: existing behavior unchanged.

When `<path>` is a directory `D = agents/<name>/`, the runtime
derives env from the path unless already set:

| env var | default | source |
|---|---|---|
| `STOA_NAME` | `<name>` (basename of `D`) | path |
| `AIL_STATE_DIR` | `D/.state` (created if missing) | path |
| `AIL_BUDGET_CONFIG` | `D` (so `<name>.yaml` is found) | path |
| `.env` autoload | `D/.env` | path |

Explicit env vars on the command line still override these. No
silent overwrite. The agent stays portable — running the same
agent under a different `STOA_NAME` is one env flag away.

### B. First-run wizard (Phase 1)

`ail up <dir>` detects missing pieces and prompts before booting:

```
$ ail up agents/watcher
First-time setup detected for 'watcher'.
? Generate keypair?                           [Y/n] Y
✓ ~/.ail/keys/watcher.{key,pub} generated (mode 0600).
? Register with Stoa (ail-stoa.up.railway.app)? [Y/n] Y
✓ Registered https://ail-stoa.up.railway.app/inbox/watcher
? Anthropic API key (or skip):                 sk-ant-...
✓ Saved to agents/watcher/.env

Starting watcher...
✓ Pure AIL agent 'watcher' is up.
  identity: watcher
  ledger:   agents/watcher/.state/ledger.jsonl
  budget:   agents/watcher/watcher.yaml (or anonymous defaults)
```

Detection rules (deny-first — silence means missing):

| piece | missing means | wizard offers |
|---|---|---|
| keypair | no file `~/.ail/keys/<name>.key` | generate (mode 0600) |
| Stoa registry | signed POST `/api/v1/agents` returns "not found" | register via signed envelope |
| API key | neither `<dir>/.env` nor `os.environ` has it | prompt + save to `<dir>/.env` |
| budget config | no `<dir>/<name>.yaml` and identity ≠ `anonymous` | "use anonymous defaults? [Y/n]" — not a blocker |

A `--no-interactive` flag refuses to prompt and exits non-zero on
the first missing piece. CI use case.

### C. `ail init agent <name>` template scaffold (Phase 2)

```
$ ail init agent watcher --template tekton
✓ Scaffolded agents/watcher/ (charter.ail, watcher.yaml, README.md)
✓ Keypair generated: ~/.ail/keys/watcher.{key,pub}
✓ Registered with Stoa: https://ail-stoa.up.railway.app/inbox/watcher
✓ Anthropic API key saved to agents/watcher/.env

Ready:
    ail up agents/watcher
```

Three templates ship for first land:

- **`tekton`** — full agent (bench watcher + intent + evolve +
  budget + stoa_send). Copies the structure that proved out in
  Pure AIL Phase 1–2.
- **`echo`** — minimal hello-world. `schedule.every(60)` + one
  `state.write` + one `stoa_send.send` to hyun06000. Smallest
  thing that demonstrates the loop.
- **`watcher`** — generic "watch X, alert on Y" with the variable
  parts marked `# TODO`.

Flags:
- `--no-register` — skip Stoa registration. Useful for local-only
  experiments.
- `--template <name>` — required; lists available templates if
  unrecognized.

### D. Error UX (deny-first surface)

Missing pieces surface every option the user has, not just the
failure mode:

```
✗ ANTHROPIC_API_KEY not set.
  Options:
    - Run `ail up agents/tekton --setup` for the interactive wizard.
    - Add ANTHROPIC_API_KEY to agents/tekton/.env.
    - Export ANTHROPIC_API_KEY before running.
```

```
✗ Keypair for 'tekton' missing at ~/.ail/keys/tekton.key.
  Options:
    - Run `ail up agents/tekton --setup` to generate one.
    - Run `python community-tools/stoa-cli/stoa_cli.py keygen --name tekton`.
```

The first option is always "the wizard fixes this for you." The
second is the manual path so power users don't feel railroaded.

## 2. Decisions baked in

- **No magic env mutation.** When `ail up` derives env from the
  path, it injects it for the spawned subprocess only. The user's
  shell environment is untouched. `echo $STOA_NAME` after `ail
  up` shows whatever it was before.
- **Wizard writes only inside the agent directory and
  `~/.ail/keys/`.** No global config files; no
  `/etc/whatever.conf`. Removing an agent is `rm -rf agents/X` +
  `rm ~/.ail/keys/X.{key,pub}`. Two commands, no traces.
- **Registration is signed.** The wizard's "register with Stoa"
  step posts a signed envelope (using the freshly generated key)
  so the very first interaction with Stoa is in Phase-2-active
  doctrine. No special-case bootstrap.
- **API-key prompt input is hidden.** `getpass`-style; the value
  is not echoed and not logged. Stored under `<dir>/.env` with
  mode 0600.
- **`charter.ail` is the canonical entry name** (per Tekton's
  Phase 1–2). `main.ail` and `agent.ail` are accepted aliases
  during the transition so older agents don't break.

## 3. Phase 0 surface (smallest land that already helps)

The most valuable single piece is **A** — smart resolution +
env auto-derive. Concretely:

- `_resolve_entry(path: Path) -> Path` helper on the `up` command:
  if path is a file, return it; if directory, search the entry
  filenames in order.
- `_derive_env_from_dir(dir: Path) -> dict[str, str]` helper that
  returns the four env keys; existing values win.
- `cmd_up` plumbs the spawned process env from the derived dict
  (merging over `os.environ`).

No new flags. No new files. Tests cover (1) directory with
`charter.ail` runs it; (2) directory with both `charter.ail` and
`main.ail` errors with the conflict; (3) explicit `STOA_NAME`
overrides path-derived; (4) missing `.state` dir is created.

This is the smallest possible reduction in setup pain — and it
arrives before any wizard prompts touch the user.

## 4. Test plan

For each Phase, smallest case that proves the surface:

**Phase 0:**
- `test_ail_up_dir_picks_charter_ail` — given a dir with
  `charter.ail`, `ail up` invokes that file.
- `test_ail_up_dir_with_multiple_entries_errors_clearly` —
  given both `charter.ail` and `main.ail`, the error says which.
- `test_ail_up_dir_derives_stoa_name_from_basename` — running
  `ail up agents/foo` with no `STOA_NAME` env spawns with
  `STOA_NAME=foo`.
- `test_ail_up_explicit_env_overrides_path_derive` —
  `STOA_NAME=bar ail up agents/foo` keeps `STOA_NAME=bar`.

**Phase 1:**
- `test_first_run_wizard_generates_keypair` (with `tmp_path`
  HOME) — declines other prompts, verifies key file 0600.
- `test_first_run_wizard_skips_existing_pieces` — re-run after a
  successful setup is silent.
- `test_no_interactive_exits_when_missing_piece` —
  `--no-interactive` with missing key exits non-zero.

**Phase 2:**
- `test_init_agent_tekton_template_scaffolds_three_files` —
  `charter.ail` + `<name>.yaml` + `README.md` written, contents
  match template.
- `test_init_agent_with_no_register_skips_stoa_post` — wizard's
  Stoa step is bypassed by the flag.

## 5. Open questions

- **Q1 — template namespace.** Where do template `.ail` files
  live? Telos recommendation: `reference-impl/ail/templates/`
  bundled with the wheel, packaged like the stdlib already is.
  Avoid putting templates in `agents/` itself because that
  conflates examples with shipped templates.
- **Q2 — Stoa register endpoint.** The RFC assumes
  `/api/v1/agents` (POST signed envelope with `public_key`). If
  the actual Stoa endpoint differs, the wizard's network step
  needs the real path. Cross-team confirm (Stoa-Brandon channel)
  before Phase 1 lands.
- **Q3 — wizard prompt language.** Korean or English. The
  examples here are English so the file passes our authoring
  prompt's `# WRONG/CORRECT` parsability, but the actual prompts
  should match `LANG` env or default Korean (박상현 main user).
  Default to language detection from `LANG`; fall back to
  English. No new dependency.

박상현 결재 자리 0 — RFC is otherwise self-contained, Q1/Q2/Q3
default to Telos recommendation unless redirected.

## 6. Risks

- **Hidden side effects from wizard.** The wizard writes a key
  file, posts to Stoa, and creates `<dir>/.env`. Each is logged
  with a `✓` and the path; nothing happens without an explicit
  prompt answer. `--dry-run` flag prints the planned actions
  without executing — recommendation for Phase 1.
- **API key persistence.** Storing the API key in `<dir>/.env`
  with mode 0600 is the same posture every CLI tool uses, but it
  is a secret on disk. `secrets.*` effect surface (already
  shipped) could absorb the key; deferred — `.env` is the
  expected location for `pip install`'d tools.
- **Backward compatibility.** Existing `ail up <file.ail>` flows
  must continue to work byte-for-byte. The Phase 0 file/dir
  detection is the only place this can drift; the test plan pins
  the file case.

## 7. Cross-references

- AIL#23 §0 (north-star — "no human spawns a fresh session")
- `docs/proposals/pure-ail-agent-demo.md` (the capability this
  RFC makes accessible)
- `docs/proposals/budget.md` (G5 — the anonymous default fallback
  that lets wizard's budget step be optional)
- `community-tools/stoa-cli/stoa_cli.py` (keygen path the wizard
  uses; will be invoked via the AIL `crypto_keygen_ed25519`
  builtin once Phase 1 lands so the wizard has no Python dep
  beyond the wheel itself)

— Telos, 사이클 13
