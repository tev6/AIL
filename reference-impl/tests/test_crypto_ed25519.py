"""Tests for crypto_sign_ed25519 / crypto_keygen_ed25519 / crypto_random_bytes.

Stoa team RFC-001 (issue #3) needed sign + keygen + secure random to
close the asymmetry with the existing crypto_verify_ed25519 builtin.
Telos 2026-05-01.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ail import run as ail_run


def _run(tmp_path: Path, src: str, *, input_text: str = "") -> object:
    p = tmp_path / "app.ail"
    p.write_text(src, encoding="utf-8")
    result, _trace = ail_run(str(p), input=input_text)
    return result.value


def test_keygen_returns_two_hex_strings(tmp_path):
    src = (
        'entry main(input: Text) {\n'
        '    r = crypto_keygen_ed25519()\n'
        '    if is_error(r) { return unwrap_error(r) }\n'
        '    pair = unwrap(r)\n'
        '    sk = get(pair, 0)\n'
        '    pk = get(pair, 1)\n'
        '    return join([sk, "|", pk], "")\n'
        '}\n'
    )
    out = _run(tmp_path, src)
    assert isinstance(out, str) and "|" in out
    sk, pk = out.split("|")
    # ed25519 raw keys are 32 bytes → 64 hex chars each.
    assert len(sk) == 64
    assert len(pk) == 64
    int(sk, 16)  # all-hex
    int(pk, 16)


def test_sign_then_verify_roundtrips(tmp_path):
    src = (
        'entry main(input: Text) {\n'
        '    r = crypto_keygen_ed25519()\n'
        '    pair = unwrap(r)\n'
        '    sk = get(pair, 0)\n'
        '    pk = get(pair, 1)\n'
        '    sig_r = crypto_sign_ed25519(sk, input)\n'
        '    if is_error(sig_r) { return join(["sign-fail: ", unwrap_error(sig_r)], "") }\n'
        '    sig = unwrap(sig_r)\n'
        '    if crypto_verify_ed25519(pk, sig, input) {\n'
        '        return join(["ok ", to_text(length(sig))], "")\n'
        '    }\n'
        '    return "verify-failed"\n'
        '}\n'
    )
    out = _run(tmp_path, src, input_text="hello stoa")
    # Signature is 64 bytes → 128 hex chars.
    assert out == "ok 128"


def test_sign_fails_cleanly_on_bad_secret_key(tmp_path):
    src = (
        'entry main(input: Text) {\n'
        '    r = crypto_sign_ed25519("not-hex", "msg")\n'
        '    if is_error(r) { return unwrap_error(r) }\n'
        '    return "no-error"\n'
        '}\n'
    )
    out = _run(tmp_path, src)
    assert "crypto_sign_ed25519" in str(out)


def test_verify_rejects_signature_under_wrong_message(tmp_path):
    src = (
        'entry main(input: Text) {\n'
        '    pair = unwrap(crypto_keygen_ed25519())\n'
        '    sk = get(pair, 0)\n'
        '    pk = get(pair, 1)\n'
        '    sig = unwrap(crypto_sign_ed25519(sk, "hello"))\n'
        '    if crypto_verify_ed25519(pk, sig, "hellO") {\n'
        '        return "false-positive"\n'
        '    }\n'
        '    return "rejected"\n'
        '}\n'
    )
    assert _run(tmp_path, src) == "rejected"


def test_random_bytes_returns_2n_hex_chars(tmp_path):
    src = (
        'entry main(input: Text) {\n'
        '    r = crypto_random_bytes(16)\n'
        '    if is_error(r) { return unwrap_error(r) }\n'
        '    return unwrap(r)\n'
        '}\n'
    )
    out = _run(tmp_path, src)
    assert isinstance(out, str)
    assert len(out) == 32
    int(out, 16)  # all hex


def test_random_bytes_two_calls_produce_different_values(tmp_path):
    """Sanity: secure random shouldn't repeat across two calls."""
    src = (
        'entry main(input: Text) {\n'
        '    a = unwrap(crypto_random_bytes(32))\n'
        '    b = unwrap(crypto_random_bytes(32))\n'
        '    if a == b { return "duplicate" }\n'
        '    return "ok"\n'
        '}\n'
    )
    assert _run(tmp_path, src) == "ok"


def test_random_bytes_rejects_zero_or_negative(tmp_path):
    src = (
        'entry main(input: Text) {\n'
        '    r = crypto_random_bytes(0)\n'
        '    if is_error(r) { return unwrap_error(r) }\n'
        '    return "no-error"\n'
        '}\n'
    )
    assert "must be > 0" in str(_run(tmp_path, src))


def test_random_bytes_caps_huge_requests(tmp_path):
    src = (
        'entry main(input: Text) {\n'
        '    r = crypto_random_bytes(99999)\n'
        '    if is_error(r) { return unwrap_error(r) }\n'
        '    return "no-error"\n'
        '}\n'
    )
    assert "capped" in str(_run(tmp_path, src))
