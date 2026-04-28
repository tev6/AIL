# ail-rs — AIL in Rust

Third reference implementation of AIL, after Python (`reference-impl/`) and Go (`go-impl/`). Targets the same spec at `spec/08-reference-card.ai.md` (grammar v1.8).

**Why Rust:**
- Single static binary — no pip, no GOROOT.
- Fast cold start — matters for `evolve`-server workloads (Stoa, Mneme).
- Memory safety + concurrency for Phase-2 work.
- Third independent runtime is a third spec checker — divergence between three implementations is the loudest possible signal that the spec is ambiguous.

**Status (2026-04-28):** Phase-0 complete (lexer + parser + evaluator) + Phase-1 Anthropic intent adapter. `intent` declarations execute against the Anthropic Messages API when `ANTHROPIC_API_KEY` is set.

## Layout

```
rust-impl/
├── Cargo.toml
├── src/
│   ├── lib.rs       # public surface
│   ├── lexer.rs     # tokenizer
│   ├── ast.rs       # Expr/Stmt/Decl
│   ├── parser.rs    # recursive-descent
│   ├── value.rs     # ValueKind + confidence
│   ├── eval.rs      # interpreter + builtins
│   └── main.rs      # ail-rs CLI
└── tests/
    ├── lexer.rs
    ├── parser.rs
    └── eval.rs
```

## Install (one-liner, after a public release)

```
curl -fsSL https://raw.githubusercontent.com/hyun06000/AIL/main/rust-impl/install.sh | sh
```

Auto-detects platform, fetches the latest `rust-v*.*.*` release tarball (binary + `examples/` bundled), and installs `ail-rs` into `~/.local/bin`. Override with `AIL_RS_VERSION=...` or `AIL_RS_PREFIX=...`. No Rust toolchain required.

> Until the first `rust-v*.*.*` tag is cut, the installer will report "no release found" — use the dev-artifact path or build from source below.

## Build from source

```
cd rust-impl
cargo build --release
./target/release/ail-rs run examples/01_hello.ail "world"
```

Requires a stable Rust toolchain (https://rustup.rs).

## Run from a downloaded binary (no toolchain needed)

Every push to `dev`/`main` produces a release-mode binary as a GitHub Actions artifact. Tagged releases (`rust-v*.*.*`) publish the same binaries to GitHub Releases.

Field-test path (dev):
1. Open the latest [`rust` workflow run](https://github.com/hyun06000/AIL/actions/workflows/rust.yml) on `dev`.
2. Scroll to the bottom — download the artifact for your platform:
   - macOS Apple Silicon → `ail-rs-aarch64-apple-darwin`
   - macOS Intel         → `ail-rs-x86_64-apple-darwin`
   - Linux x86_64        → `ail-rs-x86_64-unknown-linux-gnu`
3. Unzip the artifact, then untar — the tarball contains both the `ail-rs` binary and a bundled `examples/` directory of smoke-test programs:
   ```
   unzip ail-rs-aarch64-apple-darwin.zip
   tar -xzf ail-rs-dev-<sha>-aarch64-apple-darwin.tar.gz
   ./ail-rs run examples/01_hello.ail "world"
   ./ail-rs run examples/02_arithmetic.ail
   # See examples/README.md for the full smoke-test set.
   ```

Release path (main): same, but from [Releases](https://github.com/hyun06000/AIL/releases) — pick the latest `rust-v*.*.*`.

## CLI

```
ail-rs tokens FILE.ail                       # dump token stream
ail-rs parse  FILE.ail                       # dump parsed Program AST (Debug)
ail-rs run [--adapter NAME] FILE.ail [INPUT] # execute the entry block
```

Adapters:

| Name        | Triggers when…                                             |
|-------------|------------------------------------------------------------|
| `anthropic` | `--adapter anthropic`, **or** the program declares `intent` and `ANTHROPIC_API_KEY` is set in the environment |

Anthropic adapter:
- Reads `ANTHROPIC_API_KEY` from env.
- Subscription tokens (`sk-ant-oat…`, issued by `claude setup-token` for Pro/Max plans) are sent via `Authorization: Bearer …`.
- Standard API keys (`sk-ant-api…`) use `X-Api-Key`.
- Detection is by token prefix — no separate env var required.
- Outbound HTTP shells out to `curl` to keep the binary minimal (no native HTTP stack).

Example:
```
$ cat hello.ail
fn shout(s: Text) -> Text { return upper(s) + "!" }
entry main(text: Text) {
    return shout(text)
}

$ ail-rs run hello.ail "hello"
HELLO!
```

## Roadmap (Tekton)

1. **Lexer**     ✅
2. **Parser + AST** ✅
3. **Evaluator** ✅ (Phase-0 — fn, entry, primitives, arithmetic, lists, ~25 builtins, attempt cascade)
4. **Single-binary release pipeline** ✅ (workflow_dispatch + tag-driven)
5. **Cross-runtime conformance suite** ✅ (same `.ail` programs run on Python / Go / Rust, results compared)
6. **`intent` Anthropic adapter** ✅ (Messages API + OAuth subscription tokens)
7. **Ollama / OpenAI adapters** — for local models and other vendors.
8. **`evolve`-as-server** — match Python runtime's HTTP/process model.
9. **Provenance** — `origin_of` / `lineage_of` / `has_intent_origin`.

The Python runtime (`reference-impl/`) remains the canonical spec source. Rust catches up subset by subset.
