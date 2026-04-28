"""mneme.* effects (Arche 2026-04-29).

Per-agent identity persistence backed by the polis's git repo.
Closes the lifecycle loop: on_dying → mneme.save (commit + push),
next gen on_birth → mneme.load (pull + read three files).

Distinct from the Mneme Stoa-style server (mneme/server.ail) — here
the namespace wraps git so each agent's identity rides on the polis's
own repository.
"""
import subprocess
from pathlib import Path

from ail import compile_source, MockAdapter
from ail.runtime import Executor


def _run(src: str, input_text: str = "x"):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": input_text}).value


def _init_repo(path: Path, with_remote: bool = True) -> str:
    """Bare-bones repo with config and (optionally) a sibling bare remote."""
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email",
                    "test@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "T"],
                   check=True, capture_output=True)
    (path / "README").write_text("init\n")
    subprocess.run(["git", "-C", str(path), "add", "README"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(path), "commit", "-q", "-m", "init"],
                   check=True, capture_output=True)

    if with_remote:
        bare = path.parent / (path.name + "_bare.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(path), "remote", "add", "origin",
                        str(bare)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(path), "push", "-q", "-u", "origin",
                        "main"], check=True, capture_output=True)
    return str(path)


# ---------- mneme.save ----------

def test_save_commits_and_pushes_existing_identity_files(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "Identity.md").write_text("# I am ergon\n")
    (tmp_path / "Will.md").write_text("# carry knowledge forward\n")

    src = f'''
entry main(input: Text) {{
    return perform mneme.save("birth snapshot", repo_path: "{repo}")
}}
'''
    out = _run(src)
    assert out["ok"] is True, out
    sha = out["value"]
    assert len(sha) == 40

    log = subprocess.run(
        ["git", "-C", repo, "log", "--oneline", "-1"],
        capture_output=True, text=True, check=True).stdout
    assert "birth snapshot" in log


def test_save_errors_when_no_identity_files(tmp_path):
    repo = _init_repo(tmp_path)
    src = f'''
entry main(input: Text) {{
    return perform mneme.save("nothing", repo_path: "{repo}")
}}
'''
    out = _run(src)
    assert out["ok"] is False
    assert "nothing to save" in out["error"]


def test_save_errors_when_not_a_git_repo(tmp_path):
    src = f'''
entry main(input: Text) {{
    return perform mneme.save("x", repo_path: "{tmp_path}")
}}
'''
    out = _run(src)
    assert out["ok"] is False
    assert "not a git repo" in out["error"]


def test_save_errors_when_nothing_changed(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "Identity.md").write_text("v1\n")
    src = f'''
entry main(input: Text) {{
    return perform mneme.save("first", repo_path: "{repo}")
}}
'''
    assert _run(src)["ok"] is True
    out2 = _run(src)
    assert out2["ok"] is False
    assert "nothing changed" in out2["error"]


# ---------- mneme.load ----------

def test_load_returns_three_files(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "Identity.md").write_text("I=ergon\n")
    (tmp_path / "Bonds.md").write_text("B=arche\n")
    (tmp_path / "Will.md").write_text("W=carry\n")
    # one save so the bare remote actually has these files
    subprocess.run(["git", "-C", repo, "add", "Identity.md", "Bonds.md", "Will.md"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "seed"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "push", "-q"],
                   check=True, capture_output=True)

    src = f'''
entry main(input: Text) {{
    return perform mneme.load(repo_path: "{repo}")
}}
'''
    out = _run(src)
    assert out["ok"] is True
    rec = out["value"]
    assert "I=ergon" in rec["identity"]
    assert "B=arche" in rec["bonds"]
    assert "W=carry" in rec["will"]


def test_load_returns_none_for_missing_files(tmp_path):
    repo = _init_repo(tmp_path, with_remote=False)
    src = f'''
entry main(input: Text) {{
    return perform mneme.load(repo_path: "{repo}")
}}
'''
    out = _run(src)
    assert out["ok"] is True
    rec = out["value"]
    assert rec["identity"] is None
    assert rec["bonds"] is None
    assert rec["will"] is None


def test_load_works_without_remote(tmp_path):
    """Local-only mneme is still useful for single-machine experimentation."""
    repo = _init_repo(tmp_path, with_remote=False)
    (tmp_path / "Identity.md").write_text("local-only\n")
    src = f'''
entry main(input: Text) {{
    return perform mneme.load(repo_path: "{repo}")
}}
'''
    out = _run(src)
    assert out["ok"] is True
    assert "local-only" in out["value"]["identity"]


# ---------- mneme.log ----------

def test_log_returns_commits_for_identity_files(tmp_path):
    repo = _init_repo(tmp_path, with_remote=False)
    (tmp_path / "Identity.md").write_text("v1\n")
    subprocess.run(["git", "-C", repo, "add", "Identity.md"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "identity v1"],
                   check=True, capture_output=True)
    (tmp_path / "Identity.md").write_text("v2\n")
    subprocess.run(["git", "-C", repo, "add", "Identity.md"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", repo, "commit", "-q", "-m", "identity v2"],
                   check=True, capture_output=True)

    src = f'''
entry main(input: Text) {{
    return perform mneme.log(repo_path: "{repo}")
}}
'''
    out = _run(src)
    assert out["ok"] is True
    msgs = [r["message"] for r in out["value"]]
    assert "identity v2" in msgs
    assert "identity v1" in msgs
    # The non-identity "init" commit is filtered out
    assert "init" not in msgs


def test_log_respects_limit(tmp_path):
    repo = _init_repo(tmp_path, with_remote=False)
    (tmp_path / "Identity.md").write_text("v1\n")
    for i in range(5):
        (tmp_path / "Identity.md").write_text(f"v{i}\n")
        subprocess.run(["git", "-C", repo, "add", "Identity.md"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "-m", f"v{i}"],
                       check=True, capture_output=True)
    src = f'''
entry main(input: Text) {{
    return perform mneme.log(2, repo_path: "{repo}")
}}
'''
    out = _run(src)
    assert out["ok"] is True
    assert len(out["value"]) == 2


# ---------- on_dying lifecycle hook ----------

def test_on_dying_helper_dispatches():
    """The new on_dying hook flows through the same convention helper as
    the other lifecycle hooks (on_genesis, on_birth, before_tick, ...).
    """
    src = '''
fn on_dying(reason: Text, history: [Any]) -> Text {
    return reason
}
entry main(input: Text) { return "ok" }
'''
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    from ail.runtime.executor import ConfidentValue
    cv = ex._invoke_lifecycle_hook(
        "on_dying",
        [ConfidentValue("rollback_on fired", 1.0),
         ConfidentValue([{"i": 0}], 1.0)])
    assert cv is not None
    assert cv.value == "rollback_on fired"


def test_on_dying_absent_is_noop():
    src = 'entry main(input: Text) { return "ok" }'
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    assert ex._invoke_lifecycle_hook("on_dying", []) is None
