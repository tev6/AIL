#!/bin/sh
# ail-rs installer — Ollama-style one-liner.
#
#   curl -fsSL https://raw.githubusercontent.com/hyun06000/AIL/main/rust-impl/install.sh | sh
#
# Detects OS + arch, fetches the latest `rust-v*.*.*` release from
# GitHub, drops the `ail-rs` binary into ~/.local/bin (no sudo).
#
# Override:
#   AIL_RS_VERSION=rust-v0.1.0 sh install.sh   # pin a version
#   AIL_RS_PREFIX=/usr/local/bin sh install.sh # custom install dir
#                                              # (sudo may be required)

set -eu

REPO="hyun06000/AIL"
PREFIX="${AIL_RS_PREFIX:-${HOME}/.local/bin}"
VERSION="${AIL_RS_VERSION:-}"

red()   { printf "\033[31m%s\033[0m\n" "$1" >&2; }
green() { printf "\033[32m%s\033[0m\n"  "$1"; }
info()  { printf "  %s\n" "$1"; }
die()   { red "error: $1"; exit 1; }

# 1. detect platform → target triple
os="$(uname -s)"
arch="$(uname -m)"
case "${os}-${arch}" in
  Darwin-arm64)  target="aarch64-apple-darwin" ;;
  Darwin-x86_64) target="x86_64-apple-darwin"  ;;
  Linux-x86_64)  target="x86_64-unknown-linux-gnu" ;;
  Linux-aarch64) die "Linux aarch64 is not built yet — open an issue or build from source (cd rust-impl && cargo build --release)" ;;
  *) die "unsupported platform: ${os} ${arch}. Build from source: https://github.com/${REPO}/tree/main/rust-impl" ;;
esac

# 2. resolve version (latest rust-v* tag if not pinned)
if [ -z "${VERSION}" ]; then
  info "Looking up latest rust-v* release ..."
  # Plain tag list — works without auth, no jq required.
  VERSION="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases?per_page=30" \
    | grep -oE '"tag_name":[[:space:]]*"rust-v[0-9]+\.[0-9]+\.[0-9]+"' \
    | head -1 \
    | sed 's/.*"\(rust-v[0-9.]*\)"/\1/')"
  [ -n "${VERSION}" ] || die "no rust-v*.*.* release found yet — try setting AIL_RS_VERSION, or build from source"
fi

green "Installing ail-rs ${VERSION} for ${target}"

# 3. download + verify
TMPDIR_LOCAL="$(mktemp -d 2>/dev/null || mktemp -d -t 'ail-rs')"
trap 'rm -rf "${TMPDIR_LOCAL}"' EXIT

ARCHIVE="ail-rs-${VERSION}-${target}.tar.gz"
URL="https://github.com/${REPO}/releases/download/${VERSION}/${ARCHIVE}"
info "Downloading ${URL}"

if ! curl -fsSL --retry 3 -o "${TMPDIR_LOCAL}/${ARCHIVE}" "${URL}"; then
  die "download failed — release exists but artifact ${ARCHIVE} not found. Check https://github.com/${REPO}/releases/tag/${VERSION}"
fi

# 4. extract + install
tar -xzf "${TMPDIR_LOCAL}/${ARCHIVE}" -C "${TMPDIR_LOCAL}"
[ -f "${TMPDIR_LOCAL}/ail-rs" ] || die "archive did not contain ail-rs binary"

mkdir -p "${PREFIX}" || die "cannot create ${PREFIX}"
install -m 0755 "${TMPDIR_LOCAL}/ail-rs" "${PREFIX}/ail-rs"

# 5. confirm + PATH hint
green "Installed: ${PREFIX}/ail-rs"
"${PREFIX}/ail-rs" 2>&1 | sed 's/^/  /' | head -5 || true

case ":${PATH}:" in
  *":${PREFIX}:"*) : ;;
  *)
    cat <<EOF

  ${PREFIX} is not on your PATH yet. Add this to your shell profile:

      export PATH="${PREFIX}:\$PATH"

  Then open a new shell and run \`ail-rs\`.
EOF
    ;;
esac

cat <<EOF

Quick start:
  ail-rs run https://raw.githubusercontent.com/${REPO}/main/rust-impl/examples/01_hello.ail   # (download a sample first)
  # — or —
  ail-rs run path/to/your/program.ail

EOF
