"""gh.* effects (Arche 2026-04-28).

Named effects over `gh` CLI: pr_list / pr_view / pr_create / issue_list.
Why a `gh.*` namespace instead of generic `process.spawn`: ledger
의미 보존. `process.spawn("gh",...)` leaves "shell did something" in
the trace; `gh.pr_create(...)` leaves "PR was created" — auditable
across generations.

Tests mock subprocess.run so they pass without gh installed/authed.
"""
from unittest.mock import patch
import json
import subprocess

from ail import compile_source, MockAdapter
from ail.runtime import Executor


def _run(src: str):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": "x"}).value


def _gh_ok(stdout: str):
    """Build a CompletedProcess that mimics a successful gh call."""
    return subprocess.CompletedProcess(
        args=["gh"], returncode=0, stdout=stdout, stderr="")


def _gh_fail(stderr: str, code: int = 1):
    return subprocess.CompletedProcess(
        args=["gh"], returncode=code, stdout="", stderr=stderr)


# ---------- gh.pr_list ----------

def test_pr_list_returns_records():
    payload = json.dumps([
        {"number": 12, "title": "x", "state": "OPEN",
         "headRefName": "feat/x", "baseRefName": "main",
         "url": "https://github.com/o/r/pull/12",
         "author": {"login": "alice"}}])
    src = '''
entry main(input: Text) {
    return perform gh.pr_list("o/r")
}
'''
    with patch("subprocess.run", return_value=_gh_ok(payload)) as m:
        out = _run(src)
    assert out["ok"] is True
    prs = out["value"]
    assert len(prs) == 1
    assert prs[0]["number"] == 12
    assert prs[0]["author"] == "alice"
    # gh CLI was actually invoked with -R repo
    cmd = m.call_args.args[0]
    assert cmd[0] == "gh" and "-R" in cmd and "o/r" in cmd


def test_pr_list_state_kwarg_passes_through():
    src = '''
entry main(input: Text) {
    return perform gh.pr_list("o/r", state: "closed", limit: 5)
}
'''
    with patch("subprocess.run", return_value=_gh_ok("[]")) as m:
        out = _run(src)
    assert out["ok"] is True
    cmd = m.call_args.args[0]
    assert "--state" in cmd and "closed" in cmd
    assert "--limit" in cmd and "5" in cmd


def test_pr_list_gh_missing_returns_error():
    src = '''
entry main(input: Text) {
    return perform gh.pr_list()
}
'''
    with patch("subprocess.run", side_effect=FileNotFoundError):
        out = _run(src)
    assert out["ok"] is False
    assert "gh CLI not installed" in out["error"]


def test_pr_list_nonzero_exit_returns_error():
    src = '''
entry main(input: Text) {
    return perform gh.pr_list()
}
'''
    with patch("subprocess.run",
               return_value=_gh_fail("not authenticated\n", code=4)):
        out = _run(src)
    assert out["ok"] is False
    assert "not authenticated" in out["error"]


# ---------- gh.pr_view ----------

def test_pr_view_returns_single_record():
    payload = json.dumps({
        "number": 7, "title": "fix", "body": "details",
        "state": "MERGED",
        "headRefName": "fix/x", "baseRefName": "main",
        "url": "https://github.com/o/r/pull/7",
        "author": {"login": "bob"}})
    src = '''
entry main(input: Text) {
    return perform gh.pr_view(7, "o/r")
}
'''
    with patch("subprocess.run", return_value=_gh_ok(payload)):
        out = _run(src)
    assert out["ok"] is True
    pr = out["value"]
    assert pr["number"] == 7
    assert pr["body"] == "details"
    assert pr["author"] == "bob"


def test_pr_view_requires_number():
    src = '''
entry main(input: Text) {
    return perform gh.pr_view()
}
'''
    with patch("subprocess.run", return_value=_gh_ok("{}")):
        out = _run(src)
    assert out["ok"] is False
    assert "number required" in out["error"]


# ---------- gh.pr_create ----------

def test_pr_create_returns_url():
    src = '''
entry main(input: Text) {
    return perform gh.pr_create("Title", "Body", "o/r", base: "main", head: "ergon")
}
'''
    stdout = "Creating pull request for ergon into main\nhttps://github.com/o/r/pull/42\n"
    with patch("subprocess.run", return_value=_gh_ok(stdout)) as m:
        out = _run(src)
    assert out["ok"] is True
    assert out["value"] == "https://github.com/o/r/pull/42"
    cmd = m.call_args.args[0]
    assert "--title" in cmd and "Title" in cmd
    assert "--body" in cmd and "Body" in cmd
    assert "--base" in cmd and "main" in cmd
    assert "--head" in cmd and "ergon" in cmd


def test_pr_create_missing_args():
    src = '''
entry main(input: Text) {
    return perform gh.pr_create("only_title")
}
'''
    with patch("subprocess.run", return_value=_gh_ok("")):
        out = _run(src)
    assert out["ok"] is False
    assert "title and body required" in out["error"]


def test_pr_create_draft_kwarg():
    src = '''
entry main(input: Text) {
    return perform gh.pr_create("T", "B", draft: true)
}
'''
    stdout = "https://github.com/o/r/pull/9\n"
    with patch("subprocess.run", return_value=_gh_ok(stdout)) as m:
        out = _run(src)
    assert out["ok"] is True
    cmd = m.call_args.args[0]
    assert "--draft" in cmd


# ---------- gh.issue_list ----------

def test_issue_list_returns_records_with_labels():
    payload = json.dumps([
        {"number": 100, "title": "bug", "state": "OPEN",
         "url": "https://github.com/o/r/issues/100",
         "author": {"login": "carol"},
         "labels": [{"name": "bug"}, {"name": "p1"}]}])
    src = '''
entry main(input: Text) {
    return perform gh.issue_list("o/r")
}
'''
    with patch("subprocess.run", return_value=_gh_ok(payload)):
        out = _run(src)
    assert out["ok"] is True
    issues = out["value"]
    assert len(issues) == 1
    assert issues[0]["number"] == 100
    assert issues[0]["labels"] == ["bug", "p1"]
