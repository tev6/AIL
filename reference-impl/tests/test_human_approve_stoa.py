"""human.approve Stoa-channel integration (Arche #6, ergon 2026-04-27).

When STOA_BASE_URL is set and recipients are available (via `notify=`
kwarg or `git config ail.identity`), human.approve POSTs an approval
letter to Stoa and polls for replies. First decision (UI or Stoa) wins.

We stub the network calls by monkey-patching the executor's
`_stoa_post_approval` and `_stoa_check_approval_reply` helpers — the
goal is to verify wiring (which channel decided, what value flows
through), not to validate Stoa's HTTP semantics (those have their own
tests in stoa/).
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from ail import compile_source
from ail.runtime.executor import Executor
from ail.runtime.model import MockAdapter


def _run(src: str, inp: str = ""):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": inp}).value, ex


@pytest.fixture()
def approval_dir(tmp_path, monkeypatch):
    d = tmp_path / "approvals"
    d.mkdir()
    monkeypatch.setenv("AIL_APPROVAL_DIR", str(d))
    return d


@pytest.fixture()
def stoa_env(monkeypatch):
    monkeypatch.setenv("STOA_BASE_URL", "http://stoa.test/api/v1")
    return "http://stoa.test/api/v1"


def test_stoa_only_mode_approves_via_reply(stoa_env, monkeypatch):
    """No AIL_APPROVAL_DIR, but STOA_BASE_URL + notify list → Stoa is the
    sole channel. Reply with `approve` → Result-ok."""
    monkeypatch.delenv("AIL_APPROVAL_DIR", raising=False)

    posted = {}
    replies = {"hits": 0}

    def fake_post(self, base, recipients, plan, approval_id):
        posted["base"] = base
        posted["recipients"] = list(recipients)
        posted["plan"] = plan
        posted["approval_id"] = approval_id
        return "msg_test_123"

    def fake_check(self, base, msg_id):
        replies["hits"] += 1
        if replies["hits"] >= 2:  # first poll = empty, then approve
            return ("approved", "go ahead")
        return None

    monkeypatch.setattr(Executor, "_stoa_post_approval", fake_post)
    monkeypatch.setattr(Executor, "_stoa_check_approval_reply", fake_check)

    src = '''
entry main(input: Text) {
    r = perform human.approve("ship the release", notify: ["hyun06000"])
    if is_error(r) { return "ERR" }
    rec = unwrap(r)
    return join(["OK:", to_text(get(rec, "comment"))], "")
}
'''
    out, _ = _run(src)
    assert out == "OK:go ahead"
    assert posted["recipients"] == ["hyun06000"]
    assert "ship the release" in posted["plan"]


def test_stoa_only_mode_declines_via_reply(stoa_env, monkeypatch):
    monkeypatch.delenv("AIL_APPROVAL_DIR", raising=False)
    monkeypatch.setattr(
        Executor, "_stoa_post_approval",
        lambda self, b, r, p, a: "msg_x")
    monkeypatch.setattr(
        Executor, "_stoa_check_approval_reply",
        lambda self, b, m: ("declined", "title is wrong"))
    src = '''
entry main(input: Text) {
    r = perform human.approve("post draft", notify: ["hyun06000"])
    if is_error(r) { return unwrap_error(r) }
    return "OK"
}
'''
    out, _ = _run(src)
    assert "user declined" in out
    assert "title is wrong" in out


def test_no_channel_no_recipients_clean_error(stoa_env, monkeypatch):
    """STOA_BASE_URL set but no notify list AND no git ail.identity AND
    no AIL_APPROVAL_DIR → Stoa channel can't pick a recipient, so we
    fall through to the no-channel error."""
    monkeypatch.delenv("AIL_APPROVAL_DIR", raising=False)
    monkeypatch.setattr(
        Executor, "_git_ail_identity_list",
        lambda self: [])
    src = '''
entry main(input: Text) {
    r = perform human.approve("plan")
    if is_error(r) { return unwrap_error(r) }
    return "OK"
}
'''
    out, _ = _run(src)
    assert "no channel available" in out


def test_ui_decision_wins_when_both_active(approval_dir, stoa_env, monkeypatch):
    """Both UI and Stoa channels active. UI returns Approved before
    Stoa replies → ok, no Stoa reply consulted."""
    stoa_check_count = {"n": 0}
    monkeypatch.setattr(
        Executor, "_stoa_post_approval",
        lambda self, b, r, p, a: "msg_x")

    def slow_check(self, b, m):
        stoa_check_count["n"] += 1
        return None  # Stoa never decides

    monkeypatch.setattr(Executor, "_stoa_check_approval_reply", slow_check)

    def _ui_approve_after():
        time.sleep(0.2)
        path = approval_dir / "pending.json"
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if path.is_file():
                break
            time.sleep(0.05)
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "approved"
        data["comment"] = "via UI"
        path.write_text(json.dumps(data), encoding="utf-8")
    threading.Thread(target=_ui_approve_after, daemon=True).start()

    src = '''
entry main(input: Text) {
    r = perform human.approve("multi-channel", notify: ["hyun06000"])
    if is_error(r) { return "ERR" }
    rec = unwrap(r)
    return join(["UI:", to_text(get(rec, "comment"))], "")
}
'''
    out, _ = _run(src)
    assert out == "UI:via UI"
    # Stoa was polled at least once, but never decided.
    assert stoa_check_count["n"] >= 1


def test_timeout_env_var_respected(stoa_env, monkeypatch):
    monkeypatch.delenv("AIL_APPROVAL_DIR", raising=False)
    monkeypatch.setenv("AIL_APPROVE_TIMEOUT_S", "0.5")
    monkeypatch.setattr(
        Executor, "_stoa_post_approval",
        lambda self, b, r, p, a: "msg_x")
    monkeypatch.setattr(
        Executor, "_stoa_check_approval_reply",
        lambda self, b, m: None)  # never decides
    src = '''
entry main(input: Text) {
    r = perform human.approve("x", notify: ["who"])
    if is_error(r) { return unwrap_error(r) }
    return "OK"
}
'''
    start = time.monotonic()
    out, _ = _run(src)
    elapsed = time.monotonic() - start
    assert "timed out" in out
    assert elapsed < 2.0  # was 600s default; now ~0.5s


def test_notify_falls_back_to_git_identity(stoa_env, monkeypatch):
    monkeypatch.delenv("AIL_APPROVAL_DIR", raising=False)
    monkeypatch.setattr(
        Executor, "_git_ail_identity_list",
        lambda self: ["ergon"])
    captured_recipients = {}

    def fake_post(self, base, recipients, plan, approval_id):
        captured_recipients["r"] = list(recipients)
        return "msg_x"

    monkeypatch.setattr(Executor, "_stoa_post_approval", fake_post)
    monkeypatch.setattr(
        Executor, "_stoa_check_approval_reply",
        lambda self, b, m: ("approved", ""))

    src = '''
entry main(input: Text) {
    r = perform human.approve("no-notify-arg")
    if is_error(r) { return "ERR" }
    return "OK"
}
'''
    out, _ = _run(src)
    assert out == "OK"
    assert captured_recipients["r"] == ["ergon"]
