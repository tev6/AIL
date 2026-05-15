"""Tests for argon2id password builtins — `crypto_hash_password` and
`crypto_verify_password` (issue #8, 사이클 11 land).

These two builtins unblock Mneme RFC-001 §5 (per-identity password auth).
Surface: PHC string in/out; verify returns ok(True)/ok(False) for any
match/mismatch path (including malformed PHC) so callers pattern-match
on a single Result shape.
"""
from __future__ import annotations

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str) -> dict:
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": ""}).value


def test_hash_then_verify_correct_returns_true():
    result = _run(
        'entry main(input: Text) {\n'
        '  h_r = crypto_hash_password("hunter2")\n'
        '  phc = unwrap(h_r)\n'
        '  v_r = crypto_verify_password("hunter2", phc)\n'
        '  return unwrap(v_r)\n'
        '}\n'
    )
    assert result is True


def test_verify_wrong_password_returns_false():
    result = _run(
        'entry main(input: Text) {\n'
        '  h_r = crypto_hash_password("right")\n'
        '  phc = unwrap(h_r)\n'
        '  v_r = crypto_verify_password("wrong", phc)\n'
        '  return unwrap(v_r)\n'
        '}\n'
    )
    assert result is False


def test_verify_invalid_phc_returns_false_not_error():
    # Malformed PHC must NOT raise — caller pattern-matches a single
    # Result shape for any failure path. The verify result is just
    # ok(False) regardless of WHY it failed.
    result = _run(
        'entry main(input: Text) {\n'
        '  v_r = crypto_verify_password("anything", "not-a-phc-string")\n'
        '  return unwrap(v_r)\n'
        '}\n'
    )
    assert result is False


def test_hash_output_is_phc_argon2id_string():
    # The hash output must be a recognizable argon2id PHC string so
    # downstream tooling (Mneme, debugging, key rotation) can parse it.
    result = _run(
        'entry main(input: Text) {\n'
        '  r = crypto_hash_password("pw")\n'
        '  return unwrap(r)\n'
        '}\n'
    )
    assert isinstance(result, str)
    assert result.startswith("$argon2id$")
    assert "$v=19$" in result


def test_hash_is_salted_so_same_input_yields_different_hashes():
    # Two calls to hash the same plaintext must produce different PHC
    # strings because the salt is randomized — this is the property
    # that makes the hash safe against rainbow-table attacks. Both
    # must verify against the original.
    result = _run(
        'entry main(input: Text) {\n'
        '  a_r = crypto_hash_password("same")\n'
        '  b_r = crypto_hash_password("same")\n'
        '  a = unwrap(a_r)\n'
        '  b = unwrap(b_r)\n'
        '  v_a_r = crypto_verify_password("same", a)\n'
        '  v_b_r = crypto_verify_password("same", b)\n'
        '  return join([a, "|", b, "|", to_text(unwrap(v_a_r)), "|", to_text(unwrap(v_b_r))], "")\n'
        '}\n'
    )
    parts = result.split("|")
    a, b, va, vb = parts
    assert a != b
    assert va == "true"
    assert vb == "true"


def test_hash_missing_arg_returns_error():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = crypto_hash_password()\n'
        '  return r\n'
        '}\n'
    )
    assert isinstance(result, dict)
    assert result.get("ok") is False
    assert "crypto_hash_password" in result.get("error", "")


def test_verify_missing_args_returns_error():
    result = _run(
        'entry main(input: Text) {\n'
        '  r = crypto_verify_password("only-one")\n'
        '  return r\n'
        '}\n'
    )
    assert isinstance(result, dict)
    assert result.get("ok") is False
    assert "crypto_verify_password" in result.get("error", "")
