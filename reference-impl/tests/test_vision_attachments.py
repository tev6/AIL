"""Vision attachments — chat UI screenshot pipes through to adapter.

We don't hit real APIs; we use a capturing fake adapter and assert that
attachments are forwarded as `inputs["_attachments"]` so that
multi-modal-capable adapters (Anthropic) can rebuild image content blocks.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ail.agentic.authoring_chat import AuthoringChat
from ail.runtime.model import ModelResponse


class CapturingAdapter:
    def __init__(self):
        self.calls: list[dict] = []

    def invoke(self, *, goal, constraints, context, inputs,
               expected_type=None, examples=None) -> ModelResponse:
        self.calls.append({
            "goal_chars": len(goal or ""),
            "context": dict(context or {}),
            "inputs": dict(inputs or {}),
        })
        return ModelResponse(
            value="<reply>thanks for the image</reply>",
            confidence=0.9,
            model_id="capture-fake",
            raw={"input_tokens": 10, "output_tokens": 5},
        )


@pytest.fixture()
def project(tmp_path):
    """Minimal project fixture with the directory structure AuthoringChat needs."""
    from ail.agentic.project import Project
    p = Project.init(str(tmp_path / "demo"))
    return p


def test_attachments_forwarded_to_adapter(project):
    adapter = CapturingAdapter()
    chat = AuthoringChat(project, adapter=adapter)
    img_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    result = chat.turn(
        "이 화면 보고 다음에 뭐 누르면 돼?",
        attachments=[{"type": "image", "media_type": "image/png", "data": img_b64}],
    )
    assert len(adapter.calls) == 1
    inputs = adapter.calls[0]["inputs"]
    assert "_attachments" in inputs
    atts = inputs["_attachments"]
    assert len(atts) == 1 and atts[0]["type"] == "image"
    assert atts[0]["media_type"] == "image/png"
    assert atts[0]["data"] == img_b64
    # User text still present
    assert inputs["user_message"].startswith("이 화면 보고")
    # Reply made it back
    assert "thanks for the image" in result["reply"]


def test_no_attachments_no_key(project):
    """Without attachments, the inputs dict must NOT carry _attachments."""
    adapter = CapturingAdapter()
    chat = AuthoringChat(project, adapter=adapter)
    chat.turn("그냥 텍스트만")
    assert "_attachments" not in adapter.calls[0]["inputs"]


def test_anthropic_builds_image_content_block(monkeypatch):
    """AnthropicAdapter must convert _attachments into image content blocks
    in the messages list. We monkey-patch the SDK to capture the call."""
    captured: dict = {}

    class FakeUsage:
        input_tokens = 1
        output_tokens = 1

    class FakeResp:
        model = "claude-sonnet-4-5"
        stop_reason = "end_turn"

        def __init__(self):
            class Block:
                type = "text"
                text = "ok"
            self.content = [Block()]
            self.usage = FakeUsage()

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResp()

    class FakeClient:
        def __init__(self, **_):
            self.messages = FakeMessages()

    fake_anthropic = MagicMock()
    fake_anthropic.Anthropic = FakeClient
    monkeypatch.setitem(__import__("sys").modules, "anthropic", fake_anthropic)

    from ail.runtime.anthropic_adapter import AnthropicAdapter
    adapter = AnthropicAdapter(model="claude-sonnet-4-5", api_key="test-key")
    adapter.invoke(
        goal="g",
        constraints=[],
        context={"_intent_name": "__authoring_chat__"},
        inputs={
            "user_message": "what is this?",
            "_attachments": [{"type": "image", "media_type": "image/png", "data": "AAAA"}],
        },
    )
    msgs = captured["messages"]
    user_content = msgs[0]["content"]
    assert isinstance(user_content, list)
    assert user_content[0]["type"] == "image"
    assert user_content[0]["source"]["media_type"] == "image/png"
    assert user_content[0]["source"]["data"] == "AAAA"
    assert user_content[-1]["type"] == "text"
    assert "what is this?" in user_content[-1]["text"]
