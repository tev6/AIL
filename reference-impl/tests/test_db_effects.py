"""db.execute / db.query SQLite effects (v1.66.0).

Foundation for Stoa SQLite migration — replaces JSON-blob-load with
indexed SELECT. See Arche letter (2026-04-28) re: store.write adapter
that will eventually wrap these.
"""
from ail import compile_source, MockAdapter
from ail.runtime import Executor


def _run(src: str, db_path: str):
    program = compile_source(src)
    ex = Executor(program, MockAdapter())
    return ex.run_entry({"input": db_path}).value


def test_db_execute_creates_table_and_inserts(tmp_path):
    db = str(tmp_path / "t.db")
    src = """
entry main(input: Text) {
    r1 = perform db.execute(input,
        "CREATE TABLE m (id TEXT PRIMARY KEY, body TEXT)")
    r2 = perform db.execute(input,
        "INSERT INTO m (id, body) VALUES (?, ?)", ["a", "hello"])
    return [r1, r2]
}
"""
    out = _run(src, db)
    [r1, r2] = out
    assert r1["ok"] is True
    assert r2["ok"] is True
    assert r2["value"] == 1


def test_db_query_returns_rows(tmp_path):
    db = str(tmp_path / "t.db")
    src = """
entry main(input: Text) {
    perform db.execute(input,
        "CREATE TABLE m (id TEXT PRIMARY KEY, body TEXT)")
    perform db.execute(input, "INSERT INTO m VALUES (?, ?)", ["a", "x"])
    perform db.execute(input, "INSERT INTO m VALUES (?, ?)", ["b", "y"])
    return perform db.query(input, "SELECT id, body FROM m ORDER BY id")
}
"""
    out = _run(src, db)
    assert out["ok"] is True
    assert out["value"] == [["a", "x"], ["b", "y"]]


def test_db_query_with_params(tmp_path):
    db = str(tmp_path / "t.db")
    src = """
entry main(input: Text) {
    perform db.execute(input, "CREATE TABLE m (id TEXT, who TEXT)")
    perform db.execute(input, "INSERT INTO m VALUES (?, ?)", ["1", "ergon"])
    perform db.execute(input, "INSERT INTO m VALUES (?, ?)", ["2", "telos"])
    return perform db.query(input,
        "SELECT id FROM m WHERE who = ?", ["ergon"])
}
"""
    out = _run(src, db)
    assert out["value"] == [["1"]]


def test_db_query_empty_result(tmp_path):
    db = str(tmp_path / "t.db")
    src = """
entry main(input: Text) {
    perform db.execute(input, "CREATE TABLE m (id TEXT)")
    return perform db.query(input, "SELECT id FROM m")
}
"""
    out = _run(src, db)
    assert out["ok"] is True
    assert out["value"] == []


def test_db_execute_returns_error_on_bad_sql(tmp_path):
    db = str(tmp_path / "t.db")
    src = """
entry main(input: Text) {
    return perform db.execute(input, "BOGUS NOT SQL")
}
"""
    out = _run(src, db)
    assert out["ok"] is False
    assert "db.execute failed" in out["error"]


def test_db_query_returns_error_on_bad_sql(tmp_path):
    db = str(tmp_path / "t.db")
    src = """
entry main(input: Text) {
    return perform db.query(input, "SELECT * FROM no_such_table")
}
"""
    out = _run(src, db)
    assert out["ok"] is False


def test_db_execute_requires_path_and_sql(tmp_path):
    db = str(tmp_path / "t.db")
    src = """
entry main(input: Text) {
    return perform db.execute(input)
}
"""
    out = _run(src, db)
    assert out["ok"] is False
    assert "required" in out["error"]


def test_db_persists_across_executor_instances(tmp_path):
    db = str(tmp_path / "p.db")
    _run("""
entry main(input: Text) {
    perform db.execute(input, "CREATE TABLE k (v TEXT)")
    return perform db.execute(input, "INSERT INTO k VALUES (?)", ["A"])
}
""", db)
    out = _run("""
entry main(input: Text) {
    return perform db.query(input, "SELECT v FROM k")
}
""", db)
    assert out["value"] == [["A"]]
