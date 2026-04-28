# ail-rs — AIL in Rust

Third reference implementation of AIL, after Python (`reference-impl/`) and Go (`go-impl/`). Targets the same spec at `spec/08-reference-card.ai.md` (grammar v1.8).

**Why Rust:**
- Single static binary — no pip, no GOROOT.
- Fast cold start — matters for `evolve`-server workloads (Stoa, Mneme).
- Memory safety + concurrency for Phase-2 work.
- Third independent runtime is a third spec checker — divergence between three implementations is the loudest possible signal that the spec is ambiguous.

**Status (2026-04-28):** Phase-0 bootstrap. Lexer landed.

## Layout

```
rust-impl/
├── Cargo.toml
├── src/
│   ├── lib.rs       # public surface
│   ├── lexer.rs     # Phase-0
│   └── main.rs      # ail-rs CLI (currently: dump tokens)
└── tests/
    └── lexer.rs     # behavioral tests
```

## Build

```
cd rust-impl
cargo build --release
cargo test
```

## Roadmap (Tekton)

1. **Lexer** ✅ — port of `go-impl/lexer.go`, ~340 LOC equiv.
2. **AST + parser** — port of `go-impl/parser.go`.
3. **Evaluator** — `fn`, `entry`, primitives, arithmetic, lists, builtins.
4. **`intent`** via Anthropic / Ollama HTTP adapter.
5. **`evolve`-as-server** — match Python runtime's HTTP/process model.
6. **Cross-runtime conformance suite** — same `.ail` programs, three runtimes, byte-identical token & evaluation traces.

The Python runtime (`reference-impl/`) remains the canonical spec source. Rust catches up subset by subset.
