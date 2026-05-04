"""Tests for RFC-001 §6 stoa signing module."""
import pytest
from ail.stoa import canonical_letter, sign_envelope, _esc


class TestEsc:
    def test_backslash_first(self):
        # backslash must be escaped before others — otherwise \| becomes \\|
        assert _esc("a\\|b") == "a\\\\\\|b"

    def test_pipe(self):
        assert _esc("a|b") == "a\\|b"

    def test_semicolon(self):
        assert _esc("a;b") == "a\\;b"

    def test_colon(self):
        assert _esc("a:b") == "a\\:b"

    def test_plain(self):
        assert _esc("hello") == "hello"


class TestCanonicalLetter:
    def test_basic(self):
        msg = canonical_letter(
            "alice", "https://stoa/inbox/alice",
            [{"name": "bob", "address": "https://stoa/inbox/bob"}],
            "hello", "2026-01-01T00:00:00Z", "abc123",
        )
        assert msg.startswith("letter|")
        assert "alice" in msg
        assert "hello" in msg

    def test_recipients_sorted(self):
        msg = canonical_letter(
            "alice", "https://stoa/inbox/alice",
            [
                {"name": "zoe", "address": "https://stoa/inbox/zoe"},
                {"name": "bob", "address": "https://stoa/inbox/bob"},
            ],
            "hi", "2026-01-01T00:00:00Z", "n1",
        )
        bob_pos = msg.index("bob")
        zoe_pos = msg.index("zoe")
        assert bob_pos < zoe_pos

    def test_escape_in_content(self):
        msg = canonical_letter(
            "alice", "https://stoa/inbox/alice",
            [{"name": "bob", "address": "https://stoa/inbox/bob"}],
            "pipe|semi;colon:", "2026-01-01T00:00:00Z", "n2",
        )
        assert "pipe\\|semi\\;colon\\:" in msg


class TestSignEnvelope:
    def test_no_key_noop(self, tmp_path, monkeypatch):
        monkeypatch.setattr("ail.stoa.keys_dir", lambda: tmp_path)
        monkeypatch.setattr("ail.stoa.key_path",
                            lambda name: (tmp_path / f"{name}.key", tmp_path / f"{name}.pub"))
        env = {"from": {"name": "ghost", "address": "x"}, "to": [], "content": "hi"}
        result = sign_envelope(env.copy(), "ghost")
        assert result.get("signature") is None

    def test_with_key_adds_fields(self):
        from ail.stoa import load_sk
        # Skip if no local key (CI without bootstrap)
        if load_sk("ergon") is None:
            pytest.skip("no ergon key on this machine")

        env = {
            "from": {"name": "ergon", "address": "https://stoa/inbox/ergon"},
            "to": [{"name": "arche", "address": "https://stoa/inbox/arche"}],
            "content": "test",
        }
        result = sign_envelope(env.copy(), "ergon")
        assert result["signature"] is not None
        assert result["nonce"] is not None
        assert result["created_at"] is not None

    def test_signature_verifies(self):
        from ail.stoa import load_sk, load_pk
        if load_sk("ergon") is None:
            pytest.skip("no ergon key on this machine")

        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        env = {
            "from": {"name": "ergon", "address": "https://stoa/inbox/ergon"},
            "to": [{"name": "arche", "address": "https://stoa/inbox/arche"}],
            "content": "verify me",
        }
        signed = sign_envelope(env.copy(), "ergon")
        msg = canonical_letter(
            signed["from"]["name"], signed["from"]["address"],
            signed["to"], signed["content"],
            signed["created_at"], signed["nonce"],
        )
        pk = Ed25519PublicKey.from_public_bytes(bytes.fromhex(load_pk("ergon")))
        pk.verify(bytes.fromhex(signed["signature"]), msg.encode())
