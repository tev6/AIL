# Examples — field-test programs for `ail-rs`

Five small `.ail` programs that exercise the Phase-0 surface. Each file has a header comment with the run command and expected output, so a downloaded binary can be smoke-tested end-to-end without writing any code.

## Run

After unpacking the binary tarball:

```bash
./ail-rs run examples/01_hello.ail "world"
./ail-rs run examples/02_arithmetic.ail
./ail-rs run examples/03_list.ail
./ail-rs run examples/04_result_attempt.ail
./ail-rs run examples/05_pipeline.ail "hello,world,from,ail"
```

Or all at once (POSIX shell):

```bash
for f in examples/*.ail; do
  echo "=== $f ==="
  head -3 "$f" | sed 's|^// *||'
  ./ail-rs run "$f" "world"
  echo
done
```

| File | Tests |
|------|-------|
| `01_hello.ail`           | `entry` input arg, string `+`, `upper` builtin |
| `02_arithmetic.ail`      | recursion, `if`/`else`, arithmetic, comparisons |
| `03_list.ail`            | list literal, `for`-loop, accumulator, `xs[i]` sugar |
| `04_result_attempt.ail`  | `error()` Result envelope, `attempt`/`try` cascade |
| `05_pipeline.ail`        | `split` + `for` + `append` + `upper` + `join` |

If any output diverges from the expected line in the file header, that's a runtime regression worth investigating — the Python reference is the source of truth, so cross-check with `cd reference-impl && python -m ail run ../rust-impl/examples/<file>.ail "world"`.
