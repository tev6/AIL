# Cross-runtime conformance harness

Runs the same `.ail` corpus through every available runtime and compares stdout to the expected output declared in each program's header. Divergence between runtimes is the loudest spec-ambiguity signal we have.

## Run

```bash
bash tests/conformance/run.sh rust    # uses ail-rs (PATH or rust-impl/target)
bash tests/conformance/run.sh go      # uses go-impl/ail-go (or `go run ./go-impl`)
bash tests/conformance/run.sh python  # uses `ail` (or `python -m ail`)
```

Optional second arg: corpus directory (default `rust-impl/examples`).

Exit code is 0 when every program matches its expected output, 1 on any mismatch — CI fails the build on divergence.

## Corpus

Two corpora are exercised in CI:

- `rust-impl/examples/` (default) — the smoke-test set bundled with `ail-rs` release tarballs. Inline header directives.
- `reference-impl/tests/conformance/cases/` — the older pytest fixture set. Sidecar files.

Both formats are accepted per-program; either may be used.

### Format A — inline directives

```
// INPUT:  hello,world,from,ail
// OUTPUT: HELLO | WORLD | FROM | AIL
```

`// INPUT:` is optional. `// OUTPUT:` is required.

### Format B — sidecar files

```
foo.ail            # the program
foo.input          # optional; passed via --input
foo.expected       # required; trailing newline stripped before compare
foo.skip-<rt>      # optional; runtime ∈ {rust, go, python} skipped, body = reason
```

Mirrors the pytest harness at `reference-impl/tests/conformance/test_conformance.py` — same fixtures work in both harnesses without duplication. Inline takes precedence when both are present.

A program with neither inline `// OUTPUT:` nor `.expected` sidecar is skipped with a warning.

## Adding a new conformance program

1. Pick a corpus and format:
   - For a smoke test that ships with `ail-rs` releases → `rust-impl/examples/` + inline directives.
   - For a richer fixture (multi-line outputs, runtime-specific skip) → `reference-impl/tests/conformance/cases/` + sidecar files.
2. Run all three runtimes locally against the chosen corpus — every one must match before merging:
   ```bash
   bash tests/conformance/run.sh rust    [CORPUS]
   bash tests/conformance/run.sh go      [CORPUS]
   bash tests/conformance/run.sh python  [CORPUS]
   ```

If only one runtime matches, that's a spec-ambiguity bug — file an issue on the diverging runtime, or sharpen `spec/08-reference-card.ai.md` so all three converge.

## Runtime invocation

Three runtimes, three CLI shapes — the harness maps them transparently:

| Runtime | Command shape |
|---------|---------------|
| Rust    | `ail-rs run PROG [INPUT]`                       |
| Go      | `ail-go run PROG [--input INPUT]`               |
| Python  | `ail run --raw PROG [--input INPUT]`            |

Python's CLI prints a multi-line banner with `value:` and `confidence:` by default. `--raw` matches the go-impl/ail-rs single-line printer — same value, no decoration. The spec doesn't mandate either shape; this is a presentation choice.
