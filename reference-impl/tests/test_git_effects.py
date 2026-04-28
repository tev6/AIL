"""git.commit / git.push / git.pull effects (v1.66.2).

Foundation for Mneme=Git (Arche letter 2026-04-28). Identity / bonds /
will live as files in a git repo; lifecycle hooks (on_genesis /
on_birth / on_tick / on_dying / on_death) commit/push them at the
right phase. Auth & user.name come from ambient git config — adapter
does not pass credentials.
"""
import subprocess
from pathlib import Path

from ail import compile_source, MockAdapter
from ail.runtime import Executor


def _run(src: str, repo: str):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": repo}).value


def _init_repo(path: Path) -> str:
    """Bare-bones git repo with a single committed file and configured user."""
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
    return str(path)


def test_git_commit_creates_commit_and_returns_sha(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "x.txt").write_text("hi\n")
    src = """
entry main(input: Text) {
    return perform git.commit(input, "add x")
}
"""
    out = _run(src, repo)
    assert out["ok"] is True
    sha = out["value"]
    assert len(sha) == 40
    log = subprocess.run(
        ["git", "-C", repo, "log", "--oneline", "-1"],
        capture_output=True, text=True, check=True).stdout
    assert "add x" in log


def test_git_commit_with_specific_paths_only_stages_those(tmp_path):
    repo = _init_repo(tmp_path)
    (tmp_path / "a.txt").write_text("A\n")
    (tmp_path / "b.txt").write_text("B\n")
    src = """
entry main(input: Text) {
    return perform git.commit(input, "only a", ["a.txt"])
}
"""
    out = _run(src, repo)
    assert out["ok"] is True
    # b.txt should still be untracked
    status = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain"],
        capture_output=True, text=True, check=True).stdout
    assert "b.txt" in status


def test_git_commit_returns_error_on_no_changes(tmp_path):
    repo = _init_repo(tmp_path)
    src = """
entry main(input: Text) {
    return perform git.commit(input, "empty")
}
"""
    out = _run(src, repo)
    assert out["ok"] is False
    assert "git.commit" in out["error"]


def test_git_pull_succeeds_against_local_remote(tmp_path):
    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    # Put another commit upstream so pull has something to fetch
    (upstream / "y.txt").write_text("y\n")
    subprocess.run(["git", "-C", str(upstream), "add", "y.txt"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(upstream), "commit", "-q", "-m", "y"],
                   check=True, capture_output=True)

    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone)],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.email",
                    "c@example.com"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(clone), "config", "user.name", "C"],
                   check=True, capture_output=True)
    # Add another upstream commit so pull is non-trivial.
    (upstream / "z.txt").write_text("z\n")
    subprocess.run(["git", "-C", str(upstream), "add", "z.txt"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(upstream), "commit", "-q", "-m", "z"],
                   check=True, capture_output=True)

    src = """
entry main(input: Text) {
    return perform git.pull(input)
}
"""
    out = _run(src, str(clone))
    assert out["ok"] is True
    assert (clone / "z.txt").exists()


def test_git_push_succeeds_against_bare_remote(tmp_path):
    bare = tmp_path / "bare.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)],
                   check=True, capture_output=True)
    work = tmp_path / "work"
    _init_repo(work)
    subprocess.run(["git", "-C", str(work), "remote", "add", "origin",
                    str(bare)], check=True, capture_output=True)

    src = """
entry main(input: Text) {
    return perform git.push(input, "origin", "main")
}
"""
    out = _run(src, str(work))
    assert out["ok"] is True


def test_git_commit_requires_args(tmp_path):
    src = """
entry main(input: Text) {
    return perform git.commit(input)
}
"""
    out = _run(src, str(tmp_path))
    assert out["ok"] is False
    assert "required" in out["error"]
