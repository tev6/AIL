#!/bin/bash
# Cross-runtime conformance harness.
#
# Runs every .ail program in CORPUS through a runtime and compares stdout
# to the expected output declared in the program's header. Three runtimes
# are supported:
#
#   tests/conformance/run.sh rust   [CORPUS]   # uses ail-rs / cargo run
#   tests/conformance/run.sh go     [CORPUS]   # uses go-impl
#   tests/conformance/run.sh python [CORPUS]   # uses reference-impl
#
# CORPUS defaults to rust-impl/examples (the canonical conformance set —
# also bundled with `ail-rs` release tarballs, so a single update keeps
# field-test fixtures and conformance tests in sync).
#
# Two case formats are supported (per-program; either may be used):
#
#   (A) Inline directives in the .ail file:
#         // INPUT:  <one-line input>      (optional, empty if omitted)
#         // OUTPUT: <expected stdout>     (required)
#
#   (B) Sidecar files alongside <stem>.ail:
#         <stem>.input        (optional)
#         <stem>.expected     (required; trailing newline stripped before compare)
#         <stem>.skip-<rt>    (optional; runtime <rt> ∈ {rust,go,python} skips
#                              this case, file body used as the skip reason)
#
# Sidecar format mirrors reference-impl/tests/conformance (pytest harness),
# so the same case dir works in both harnesses without duplication.
# Inline takes precedence when both are present.
#
# Exit code: 0 if every program matches, 1 if any mismatch.

set -eu

usage() {
  echo "usage: $0 <rust|go|python> [CORPUS_DIR]" >&2
  exit 2
}

[ $# -ge 1 ] || usage
RUNTIME="$1"
CORPUS="${2:-rust-impl/examples}"

# Resolve the run command for each runtime.
case "$RUNTIME" in
  rust)
    if command -v ail-rs >/dev/null 2>&1; then
      RUN_CMD="ail-rs run"
    elif [ -x rust-impl/target/release/ail-rs ]; then
      RUN_CMD="rust-impl/target/release/ail-rs run"
    elif [ -x rust-impl/target/debug/ail-rs ]; then
      RUN_CMD="rust-impl/target/debug/ail-rs run"
    else
      echo "rust runtime not found — build it first: (cd rust-impl && cargo build --release)" >&2
      exit 2
    fi
    ;;
  go)
    if [ -x go-impl/ail-go ]; then
      RUN_CMD="go-impl/ail-go run"
    elif command -v go >/dev/null 2>&1; then
      RUN_CMD="go run ./go-impl run"
    else
      echo "go runtime not found — build it first: (cd go-impl && go build)" >&2
      exit 2
    fi
    ;;
  python)
    if command -v ail >/dev/null 2>&1; then
      RUN_CMD="ail run"
    elif command -v python >/dev/null 2>&1; then
      RUN_CMD="python -m ail run"
    elif command -v python3 >/dev/null 2>&1; then
      RUN_CMD="python3 -m ail run"
    else
      echo "python runtime not found — pip install ail-interpreter, or run from reference-impl/" >&2
      exit 2
    fi
    ;;
  *)
    usage
    ;;
esac

[ -d "$CORPUS" ] || { echo "corpus dir not found: $CORPUS" >&2; exit 2; }

echo "== conformance: ${RUNTIME} (${RUN_CMD}) on ${CORPUS} =="

shopt -s nullglob 2>/dev/null || true
fail=0
total=0
skipped=0

for prog in "${CORPUS}"/*.ail; do
  total=$((total + 1))
  stem="${prog%.ail}"

  # Per-runtime skip marker (sidecar format, mirrors pytest harness).
  skip_marker="${stem}.skip-${RUNTIME}"
  if [ -f "$skip_marker" ]; then
    reason=$(tr -d '\n' < "$skip_marker")
    [ -n "$reason" ] || reason="runtime ${RUNTIME} skip"
    echo "skip: $prog (${reason})"
    skipped=$((skipped + 1))
    continue
  fi

  # Expected output: inline // OUTPUT: takes precedence; fall back to
  # <stem>.expected sidecar if present.
  if grep -q '^// OUTPUT:' "$prog"; then
    expected=$(grep -m1 '^// OUTPUT:' "$prog" | sed -E 's|^// OUTPUT:[[:space:]]*||')
  elif [ -f "${stem}.expected" ]; then
    # Bash command substitution strips trailing newlines — matches the
    # pytest harness's .read_text().rstrip("\n") semantics.
    expected=$(cat "${stem}.expected")
  else
    echo "skip: $prog (no // OUTPUT: directive or .expected sidecar)"
    skipped=$((skipped + 1))
    continue
  fi

  # Input: inline // INPUT: takes precedence; fall back to <stem>.input.
  if grep -q '^// INPUT:' "$prog"; then
    input=$(grep -m1 '^// INPUT:' "$prog" | sed -E 's|^// INPUT:[[:space:]]*||')
  elif [ -f "${stem}.input" ]; then
    input=$(cat "${stem}.input")
  else
    input=""
  fi

  # Each runtime takes input differently:
  #   rust   — positional after the file
  #   go     — --input flag
  #   python — --input flag
  case "$RUNTIME" in
    rust)
      cmd_args=("$prog" "$input")
      ;;
    go)
      if [ -n "$input" ]; then
        cmd_args=("$prog" --input "$input")
      else
        cmd_args=("$prog")
      fi
      ;;
    python)
      # `ail run --raw` prints value-only matching go-impl's default printer
      # (the conformance fixture shape). Without --raw, ail prints a banner
      # + confidence — useful for humans, noise for cross-runtime diffing.
      if [ -n "$input" ]; then
        cmd_args=(--raw "$prog" --input "$input")
      else
        cmd_args=(--raw "$prog")
      fi
      ;;
  esac

  # Run the program. Capture stdout; stderr is shown on mismatch.
  if actual=$($RUN_CMD "${cmd_args[@]}" 2>/tmp/conformance.err); then
    if [ "$actual" = "$expected" ]; then
      printf "  pass: %s\n" "$prog"
    else
      printf "  FAIL: %s\n" "$prog"
      printf "        expected: %q\n" "$expected"
      printf "        actual:   %q\n" "$actual"
      fail=$((fail + 1))
    fi
  else
    rc=$?
    printf "  ERROR: %s (exit %s)\n" "$prog" "$rc"
    sed 's|^|        |' /tmp/conformance.err
    fail=$((fail + 1))
  fi
done

echo "------------------------------------------------------------"
passed=$((total - fail - skipped))
if [ "$skipped" -gt 0 ]; then
  echo "${passed}/${total} passed (${skipped} skipped, ${fail} failed)"
else
  echo "${passed}/${total} passed (${fail} failed)"
fi

[ "$fail" -eq 0 ] || exit 1
