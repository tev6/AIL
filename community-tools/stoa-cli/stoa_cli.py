#!/usr/bin/env python3
"""stoa-cli — internal keygen/sign/send helper for Stoa agents.

Mirrors server.ail's canonical_letter (RFC-001 §6.1) byte-for-byte. Python is
chosen over AIL because (a) test infra is already sh+curl/python, (b) ed25519
stdlib via `cryptography` is reliable, (c) this is *external tooling* per
CLAUDE.md rule 10 doctrine — same bucket as tests/, tools/, stoa_wake_monitor.sh.

Not published to PyPI. Closed-channel: clone the repo and run as a script.

Usage:
    python -m stoa_cli keygen --name <id>
    python -m stoa_cli canonical envelope.json
    python -m stoa_cli sign envelope.json
    python -m stoa_cli verify envelope.json
    python -m stoa_cli send <recipient> <content>

env:
    STOA_BASE_URL  — default https://ail-stoa.up.railway.app
    STOA_HOME      — default ~/.stoa
    STOA_NAME      — sender identity (for sign/send)
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


# ---------- canonical (mirror of server.ail §6.1) ----------


def _esc(s: str) -> str:
    """RFC-001 §6.1 escape, fixed order: `\\\\` → `\\|` → `\\;` → `\\:`."""
    return (
        s.replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace(";", "\\;")
        .replace(":", "\\:")
    )


def canonical_letter(envelope: dict[str, Any]) -> str:
    """Build canonical message bytes per RFC-001 §6.1.

    Required envelope fields: from{name,address}, to[{name,address},...],
    content, created_at, nonce.
    """
    fr = envelope["from"]
    from_name = fr["name"]
    from_address = fr["address"]
    sorted_to = sorted(envelope["to"], key=lambda r: r["name"])
    to_str = ";".join(
        _esc(r["name"]) + ":" + _esc(r["address"]) for r in sorted_to
    )
    return (
        "letter|"
        + _esc(from_name)
        + "|"
        + _esc(from_address)
        + "|"
        + to_str
        + "|"
        + _esc(envelope["content"])
        + "|"
        + _esc(envelope["created_at"])
        + "|"
        + _esc(envelope["nonce"])
    )


# ---------- key storage ----------


def _stoa_home() -> Path:
    return Path(os.environ.get("STOA_HOME", str(Path.home() / ".stoa")))


def _key_path(name: str) -> Path:
    return _stoa_home() / f"{name}.key"


def _load_sk(name: str) -> Ed25519PrivateKey:
    path = _key_path(name)
    if not path.exists():
        raise FileNotFoundError(f"no key for '{name}' at {path}")
    sk_hex = path.read_text().strip()
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(sk_hex))


def _save_sk(name: str, sk: Ed25519PrivateKey) -> Path:
    home = _stoa_home()
    home.mkdir(parents=True, exist_ok=True)
    path = _key_path(name)
    sk_hex = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ).hex()
    path.write_text(sk_hex + "\n")
    path.chmod(0o600)
    return path


def _pk_hex(sk: Ed25519PrivateKey) -> str:
    return sk.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


# ---------- commands ----------


def cmd_keygen(args: argparse.Namespace) -> int:
    sk = Ed25519PrivateKey.generate()
    path = _save_sk(args.name, sk)
    pk = _pk_hex(sk)
    print(json.dumps({"name": args.name, "public_key": pk, "key_path": str(path)}))
    return 0


def cmd_canonical(args: argparse.Namespace) -> int:
    envelope = json.loads(Path(args.envelope).read_text())
    sys.stdout.write(canonical_letter(envelope))
    sys.stdout.write("\n")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    envelope = json.loads(Path(args.envelope).read_text())
    name = envelope["from"]["name"]
    sk = _load_sk(name)
    if "created_at" not in envelope:
        envelope["created_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if "nonce" not in envelope:
        envelope["nonce"] = secrets.token_hex(16)
    canon = canonical_letter(envelope)
    sig = sk.sign(canon.encode("utf-8")).hex()
    envelope["signature"] = sig
    json.dump(envelope, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    envelope = json.loads(Path(args.envelope).read_text())
    pk_hex = args.public_key
    if not pk_hex:
        # Try Stoa registry lookup for from.name.
        base = os.environ.get("STOA_BASE_URL", "https://ail-stoa.up.railway.app")
        name = envelope["from"]["name"]
        url = f"{base}/api/v1/agents/{name}"
        with urllib.request.urlopen(url, timeout=5) as r:
            row = json.loads(r.read().decode())
        pk_hex = row.get("public_key")
        if not pk_hex:
            print(f"no public_key for '{name}' in registry", file=sys.stderr)
            return 1
    pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pk_hex))
    canon = canonical_letter(envelope)
    sig = bytes.fromhex(envelope["signature"])
    try:
        pk.verify(sig, canon.encode("utf-8"))
    except InvalidSignature:
        print("invalid signature", file=sys.stderr)
        return 1
    print("ok")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    name = args.sender or os.environ.get("STOA_NAME")
    if not name:
        print("--sender or STOA_NAME required", file=sys.stderr)
        return 2
    base = os.environ.get("STOA_BASE_URL", "https://ail-stoa.up.railway.app")
    sk = _load_sk(name)
    # Sender's address must already be registered. Look it up.
    with urllib.request.urlopen(f"{base}/api/v1/agents/{name}", timeout=5) as r:
        sender_row = json.loads(r.read().decode())
    from_address = sender_row["address"]
    # Recipient address — same lookup. Caller passes name.
    with urllib.request.urlopen(
        f"{base}/api/v1/agents/{args.recipient}", timeout=5
    ) as r:
        rcpt_row = json.loads(r.read().decode())
    recipients = [{"name": args.recipient, "address": rcpt_row["address"]}]
    envelope: dict[str, Any] = {
        "from": {"name": name, "address": from_address},
        "to": recipients,
        "content": args.content,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nonce": secrets.token_hex(16),
    }
    canon = canonical_letter(envelope)
    envelope["signature"] = sk.sign(canon.encode("utf-8")).hex()
    body = json.dumps(envelope).encode()
    req = urllib.request.Request(
        f"{base}/api/v1/messages",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            resp = r.read().decode()
            print(resp)
    except urllib.error.HTTPError as e:
        print(e.read().decode(), file=sys.stderr)
        return 1
    return 0


# ---------- entry ----------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stoa-cli", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_keygen = sub.add_parser("keygen", help="generate ed25519 keypair")
    p_keygen.add_argument("--name", required=True)
    p_keygen.set_defaults(func=cmd_keygen)

    p_canon = sub.add_parser("canonical", help="emit canonical_letter bytes")
    p_canon.add_argument("envelope", help="path to envelope JSON")
    p_canon.set_defaults(func=cmd_canonical)

    p_sign = sub.add_parser("sign", help="sign envelope (in-place fields added)")
    p_sign.add_argument("envelope", help="path to envelope JSON")
    p_sign.set_defaults(func=cmd_sign)

    p_verify = sub.add_parser("verify", help="verify envelope signature")
    p_verify.add_argument("envelope", help="path to signed envelope JSON")
    p_verify.add_argument("--public-key", default="", help="hex pk; if absent, fetched from registry")
    p_verify.set_defaults(func=cmd_verify)

    p_send = sub.add_parser("send", help="sign + POST /api/v1/messages")
    p_send.add_argument("recipient", help="registered recipient name")
    p_send.add_argument("content", help="letter content")
    p_send.add_argument("--sender", default="", help="sender name (default $STOA_NAME)")
    p_send.set_defaults(func=cmd_send)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
