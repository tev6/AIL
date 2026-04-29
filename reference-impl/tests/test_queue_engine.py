"""Tests for the append-only message queue.

Telos + Arche 2026-04-29 rebuild. Two layers exercised:
  1. queue_engine module (pure Python) — replay correctness, state
     transitions, dead-letter semantics.
  2. perform queue.* effects via ail_run — the user-visible surface.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ail import run as ail_run
from ail.runtime import queue_engine


def _records(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# ---------- engine layer ----------


def test_push_assigns_monotonic_ids(tmp_path):
    p = tmp_path / "q.jsonl"
    a = queue_engine.push(p, {"hello": "world"})
    b = queue_engine.push(p, {"hello": "again"})
    assert a == "msg_0001"
    assert b == "msg_0002"


def test_take_returns_oldest_pending_and_marks_working(tmp_path):
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    queue_engine.push(p, {"x": 2})
    payload = queue_engine.take(p)
    assert payload is not None
    assert payload["_id"] == "msg_0001"
    assert payload["x"] == 1
    assert payload["_retry_count"] == 0
    # State now has msg_0001 in working, msg_0002 in pending.
    state = queue_engine.replay(p)
    assert state["msg_0001"].state == "working"
    assert state["msg_0002"].state == "pending"


def test_take_returns_none_on_empty_queue(tmp_path):
    p = tmp_path / "q.jsonl"
    assert queue_engine.take(p) is None


def test_take_skips_already_taken_messages(tmp_path):
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    queue_engine.push(p, {"x": 2})
    a = queue_engine.take(p)
    b = queue_engine.take(p)
    assert a["_id"] == "msg_0001"
    assert b["_id"] == "msg_0002"
    # Third take is empty.
    assert queue_engine.take(p) is None


def test_done_transitions_working_to_done(tmp_path):
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    queue_engine.take(p)
    assert queue_engine.done(p, "msg_0001") is True
    state = queue_engine.replay(p)
    assert state["msg_0001"].state == "done"


def test_done_rejects_id_not_in_working(tmp_path):
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    # Without take, the id is still pending.
    assert queue_engine.done(p, "msg_0001") is False
    assert queue_engine.done(p, "nonexistent") is False


def test_retry_returns_message_to_pending_with_bumped_counter(tmp_path):
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    queue_engine.take(p)
    outcome = queue_engine.retry(p, "msg_0001", "transient network err")
    assert outcome == "retried"
    state = queue_engine.replay(p)
    assert state["msg_0001"].state == "pending"
    assert state["msg_0001"].retry_count == 1
    assert state["msg_0001"].last_reason == "transient network err"


def test_retry_count_dead_letters_at_threshold(tmp_path):
    """Same Physis rule as scheduler self-throttle: 5 consecutive
    retries → auto dead-letter."""
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    # 4 retry cycles return to pending.
    for i in range(queue_engine.DEAD_LETTER_AT - 1):
        queue_engine.take(p)
        outcome = queue_engine.retry(p, "msg_0001", f"err {i}")
        assert outcome == "retried"
    # 5th retry trips dead-letter.
    queue_engine.take(p)
    outcome = queue_engine.retry(p, "msg_0001", "final err")
    assert outcome == "dead_letter"
    state = queue_engine.replay(p)
    assert state["msg_0001"].state == "dead_letter"
    # Subsequent take cannot resurrect it.
    assert queue_engine.take(p) is None


def test_retry_rejects_non_working_messages(tmp_path):
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    # Without take, msg is pending — retry rejects.
    assert queue_engine.retry(p, "msg_0001", "x") == "wrong_state"
    assert queue_engine.retry(p, "ghost", "x") == "not_found"


def test_replay_tolerates_malformed_lines(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text(
        '{"action": "push", "id": "msg_0001", "msg": {"a": 1}}\n'
        'not json\n'
        '{"action": "garbage_action", "id": "msg_0001"}\n'
        '{"action": "take", "id": "msg_0001"}\n',
        encoding="utf-8",
    )
    state = queue_engine.replay(p)
    assert state["msg_0001"].state == "working"


def test_log_is_append_only(tmp_path):
    """Every state transition writes a record; nothing is rewritten."""
    p = tmp_path / "q.jsonl"
    queue_engine.push(p, {"x": 1})
    queue_engine.take(p)
    queue_engine.retry(p, "msg_0001", "x")
    queue_engine.take(p)
    queue_engine.done(p, "msg_0001")
    records = _records(p)
    assert [r["action"] for r in records] == [
        "push", "take", "retry", "take", "done",
    ]


# ---------- effect layer (perform queue.*) ----------


def test_perform_queue_push_writes_to_AIL_QUEUE_FILE(tmp_path, monkeypatch):
    qpath = tmp_path / "q.jsonl"
    monkeypatch.setenv("AIL_QUEUE_FILE", str(qpath))
    src = tmp_path / "app.ail"
    src.write_text(
        'entry main(input: Text) {\n'
        '    r = perform queue.push(make_record([["body", input]]))\n'
        '    return unwrap(r)\n'
        '}\n',
        encoding="utf-8",
    )
    result, _trace = ail_run(str(src), input="hello")
    assert result.value == "msg_0001"
    records = _records(qpath)
    assert records[0]["action"] == "push"
    # make_record materializes to a dict before reaching the effect,
    # so the persisted shape is `{"body": "hello"}`.
    assert records[0]["msg"] == {"body": "hello"}


def test_perform_queue_take_returns_record_with_meta_fields(
        tmp_path, monkeypatch):
    qpath = tmp_path / "q.jsonl"
    monkeypatch.setenv("AIL_QUEUE_FILE", str(qpath))
    queue_engine.push(qpath, [["body", "msg-1"]])
    src = tmp_path / "app.ail"
    src.write_text(
        'entry main(input: Text) {\n'
        '    r = perform queue.take()\n'
        '    if is_error(r) {\n'
        '        return "empty"\n'
        '    }\n'
        '    payload = unwrap(r)\n'
        '    return get(payload, "_id")\n'
        '}\n',
        encoding="utf-8",
    )
    result, _trace = ail_run(str(src), input="")
    assert result.value == "msg_0001"


def test_perform_queue_take_error_when_empty(tmp_path, monkeypatch):
    qpath = tmp_path / "q.jsonl"
    monkeypatch.setenv("AIL_QUEUE_FILE", str(qpath))
    src = tmp_path / "app.ail"
    src.write_text(
        'entry main(input: Text) {\n'
        '    r = perform queue.take()\n'
        '    if is_error(r) {\n'
        '        return "empty"\n'
        '    }\n'
        '    return "got one"\n'
        '}\n',
        encoding="utf-8",
    )
    result, _trace = ail_run(str(src), input="")
    assert result.value == "empty"


def test_perform_queue_done_clears_working_state(tmp_path, monkeypatch):
    qpath = tmp_path / "q.jsonl"
    monkeypatch.setenv("AIL_QUEUE_FILE", str(qpath))
    queue_engine.push(qpath, [["body", "x"]])
    src = tmp_path / "app.ail"
    src.write_text(
        'entry main(input: Text) {\n'
        '    taken = unwrap(perform queue.take())\n'
        '    msg_id = get(taken, "_id")\n'
        '    r = perform queue.done(msg_id)\n'
        '    return unwrap(r)\n'
        '}\n',
        encoding="utf-8",
    )
    result, _trace = ail_run(str(src), input="")
    assert result.value == "msg_0001"
    state = queue_engine.replay(qpath)
    assert state["msg_0001"].state == "done"


def test_perform_queue_retry_until_dead_letter(tmp_path, monkeypatch):
    qpath = tmp_path / "q.jsonl"
    monkeypatch.setenv("AIL_QUEUE_FILE", str(qpath))
    queue_engine.push(qpath, [["body", "flaky"]])
    # Retry 5 times — last one should dead-letter.
    src = tmp_path / "app.ail"
    src.write_text(
        'entry main(input: Text) {\n'
        '    taken = unwrap(perform queue.take())\n'
        '    msg_id = get(taken, "_id")\n'
        '    r = perform queue.retry(msg_id, input)\n'
        '    return unwrap(r)\n'
        '}\n',
        encoding="utf-8",
    )
    for i in range(queue_engine.DEAD_LETTER_AT - 1):
        result, _ = ail_run(str(src), input=f"err {i}")
        assert result.value == "retried"
    result, _ = ail_run(str(src), input="final")
    assert result.value == "dead_letter"
    state = queue_engine.replay(qpath)
    assert state["msg_0001"].state == "dead_letter"


def test_perform_queue_without_env_var_returns_explanatory_error(
        tmp_path, monkeypatch):
    monkeypatch.delenv("AIL_QUEUE_FILE", raising=False)
    src = tmp_path / "app.ail"
    src.write_text(
        'entry main(input: Text) {\n'
        '    r = perform queue.push(make_record([["body", "x"]]))\n'
        '    if is_error(r) {\n'
        '        return unwrap_error(r)\n'
        '    }\n'
        '    return unwrap(r)\n'
        '}\n',
        encoding="utf-8",
    )
    result, _trace = ail_run(str(src), input="")
    assert "AIL_QUEUE_FILE" in result.value
