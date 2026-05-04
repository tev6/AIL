"""Stoa identity helpers — ed25519 keygen, signing, key I/O.

RFC-001 §6.1 canonical format:
  letter|<from_name>|<from_addr>|<sorted_to>|<content>|<created_at>|<nonce>
  Fields escaped: backslash -> \\\\, | -> \\|, ; -> \\;, : -> \\:  (backslash first)

Usage (CLI):
  ail stoa keygen --identity ergon
"""
from __future__ import annotations
import os
import json
import secrets
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Escape / canonical
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    s = s.replace("\\", "\\\\")
    s = s.replace("|", "\\|")
    s = s.replace(";", "\\;")
    s = s.replace(":", "\\:")
    return s


def canonical_letter(
    from_name: str,
    from_address: str,
    recipients: list[dict],
    content: str,
    created_at: str,
    nonce: str,
) -> str:
    sorted_to = sorted(recipients, key=lambda r: r.get("name", ""))
    to_parts = [f"{_esc(r['name'])}:{_esc(r['address'])}" for r in sorted_to]
    to_str = ";".join(to_parts)
    return (
        "letter|"
        + _esc(from_name) + "|"
        + _esc(from_address) + "|"
        + to_str + "|"
        + _esc(content) + "|"
        + _esc(created_at) + "|"
        + _esc(nonce)
    )


# ---------------------------------------------------------------------------
# Key I/O
# ---------------------------------------------------------------------------

def keys_dir() -> Path:
    d = Path.home() / ".ail" / "keys"
    d.mkdir(parents=True, exist_ok=True)
    return d


def key_path(identity: str) -> tuple[Path, Path]:
    """Returns (sk_path, pk_path)."""
    d = keys_dir()
    return d / f"{identity}.key", d / f"{identity}.pub"


def load_sk(identity: str) -> str | None:
    sk_path, _ = key_path(identity)
    if not sk_path.exists():
        return None
    return sk_path.read_text().strip()


def load_pk(identity: str) -> str | None:
    _, pk_path = key_path(identity)
    if not pk_path.exists():
        return None
    return pk_path.read_text().strip()


# ---------------------------------------------------------------------------
# Keygen
# ---------------------------------------------------------------------------

def keygen(identity: str, stoa_url: str, dry_run: bool = False) -> dict:
    """Generate ed25519 key pair, save to ~/.ail/keys/, register public key
    on Stoa.  Returns {"pk_hex": ..., "sk_path": ..., "pk_path": ...,
    "registered": bool}.
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()

    sk_bytes = sk.private_bytes_raw()
    pk_bytes = pk.public_bytes_raw()
    sk_hex = sk_bytes.hex()
    pk_hex = pk_bytes.hex()

    sk_path, pk_path = key_path(identity)
    sk_path.write_text(sk_hex + "\n")
    os.chmod(sk_path, 0o600)
    pk_path.write_text(pk_hex + "\n")
    os.chmod(pk_path, 0o644)

    registered = False
    if not dry_run and stoa_url:
        registered = _register_pubkey(stoa_url, identity, pk_hex)

    return {
        "pk_hex": pk_hex,
        "sk_path": str(sk_path),
        "pk_path": str(pk_path),
        "registered": registered,
    }


def _register_pubkey(stoa_url: str, identity: str, pk_hex: str) -> bool:
    base = stoa_url.rstrip("/")
    # Fetch current address from registry
    try:
        with urllib.request.urlopen(f"{base}/api/v1/agents/{identity}", timeout=8) as r:
            agent = json.loads(r.read())
        address = agent.get("address", f"{base}/inbox/{identity}")
    except Exception:
        address = f"{base}/inbox/{identity}"

    payload = json.dumps({"name": identity, "address": address, "public_key": pk_hex}).encode()
    req = urllib.request.Request(
        f"{base}/api/v1/agents",
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8):
            pass
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------

def sign_envelope(
    envelope: dict,
    identity: str,
) -> dict:
    """Add RFC-001 §6 signature fields to envelope dict in-place.
    Loads sk from ~/.ail/keys/<identity>.key.
    Returns envelope (mutated). No-ops if key not found.
    """
    sk_hex = load_sk(identity)
    if not sk_hex:
        return envelope

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sk_bytes = bytes.fromhex(sk_hex)
        sk = Ed25519PrivateKey.from_private_bytes(sk_bytes)

        from_name = envelope.get("from", {}).get("name", identity)
        from_address = envelope.get("from", {}).get("address", "")
        recipients = envelope.get("to", [])
        content = envelope.get("content", "")
        created_at = envelope.get("created_at") or datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        nonce = secrets.token_hex(32)

        msg = canonical_letter(from_name, from_address, recipients, content, created_at, nonce)
        sig_bytes = sk.sign(msg.encode("utf-8"))
        sig_hex = sig_bytes.hex()

        envelope["created_at"] = created_at
        envelope["nonce"] = nonce
        envelope["signature"] = sig_hex
    except Exception:
        pass  # signing failure must not block delivery

    return envelope


# ---------------------------------------------------------------------------
# Stoa identity resolution
# ---------------------------------------------------------------------------

def resolve_identity() -> str | None:
    """Return current agent identity from git config or env."""
    import subprocess
    # Try worktree-scoped first, then global
    for scope in (["git", "config", "--worktree", "--get", "ail.identity"],
                  ["git", "config", "--get", "ail.identity"]):
        try:
            r = subprocess.run(scope, capture_output=True, text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return os.environ.get("AIL_IDENTITY")
