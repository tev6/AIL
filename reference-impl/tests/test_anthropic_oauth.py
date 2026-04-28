"""Anthropic adapter OAuth subscription token detection (v1.66.1).

Pro/Max plan users get OAuth tokens via `claude setup-token`. They start
with `sk-ant-oat01` and must be sent as `Authorization: Bearer …`
(SDK's `auth_token=…`) instead of `X-Api-Key` (SDK's `api_key=…`).
Detection is by prefix so users don't need a separate env var.
"""
from unittest.mock import patch
import pytest

from ail.runtime.anthropic_adapter import AnthropicAdapter


def test_api_key_prefix_routes_to_api_key_param():
    a = AnthropicAdapter(api_key="sk-ant-api03-test")
    assert a._is_oauth is False
    assert a._token == "sk-ant-api03-test"


def test_oauth_prefix_routes_to_auth_token_param():
    a = AnthropicAdapter(api_key="sk-ant-oat01-test")
    assert a._is_oauth is True
    assert a._token == "sk-ant-oat01-test"


def test_missing_token_raises():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            AnthropicAdapter()


def test_env_var_token_detected_correctly():
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-oat01-fromenv"},
                    clear=True):
        a = AnthropicAdapter()
        assert a._is_oauth is True


def test_invoke_uses_auth_token_for_oauth(monkeypatch):
    """Smoke: when the token is OAuth, the SDK is constructed with
    auth_token=…, not api_key=…. We patch anthropic.Anthropic to a spy
    so we don't make a real network call."""
    captured = {}

    class _SpyClient:
        def __init__(self, **kwargs):
            captured["init_kwargs"] = kwargs
            self.messages = self
        def create(self, **kwargs):
            class _R:
                content = []
                stop_reason = "end_turn"
                model = "claude-sonnet-4-5"
                class usage:
                    input_tokens = 1
                    output_tokens = 1
            return _R()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _SpyClient)

    a = AnthropicAdapter(api_key="sk-ant-oat01-spy")
    a.invoke(goal="g", constraints=[], context={}, inputs={"x": 1})
    assert "auth_token" in captured["init_kwargs"]
    assert "api_key" not in captured["init_kwargs"]
    assert captured["init_kwargs"]["auth_token"] == "sk-ant-oat01-spy"


def test_invoke_uses_api_key_for_standard_token(monkeypatch):
    captured = {}

    class _SpyClient:
        def __init__(self, **kwargs):
            captured["init_kwargs"] = kwargs
            self.messages = self
        def create(self, **kwargs):
            class _R:
                content = []
                stop_reason = "end_turn"
                model = "claude-sonnet-4-5"
                class usage:
                    input_tokens = 1
                    output_tokens = 1
            return _R()

    import anthropic
    monkeypatch.setattr(anthropic, "Anthropic", _SpyClient)

    a = AnthropicAdapter(api_key="sk-ant-api03-spy")
    a.invoke(goal="g", constraints=[], context={}, inputs={"x": 1})
    assert "api_key" in captured["init_kwargs"]
    assert "auth_token" not in captured["init_kwargs"]
