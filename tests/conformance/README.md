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

The default corpus lives at `rust-impl/examples/`. The same files ship in `ail-rs` release tarballs as smoke tests, so a single update keeps both pinned to the same expected behavior.

Each `.ail` has a header with two machine-readable directives:

```
// INPUT:  hello,world,from,ail
// OUTPUT: HELLO | WORLD | FROM | AIL
```

`// INPUT:` is optional (empty if omitted). `// OUTPUT:` is required — programs without it are skipped with a warning.

## Adding a new conformance program

1. Drop the `.ail` file into `rust-impl/examples/` (so it ships with releases too).
2. Add the two directives at the top.
3. Run all three runtimes locally — every one must match before merging:
   ```bash
   bash tests/conformance/run.sh rust
   bash tests/conformance/run.sh go
   bash tests/conformance/run.sh python
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
