//! Evaluator behavioral tests. Mirrors `go-impl/eval_test.go` and the
//! Python `reference-impl/tests/test_executor*.py` cases as Tekton lands them.

use ail::{run, Value, ValueKind};

fn run_ok(src: &str, input: &str) -> Value {
    run(src, input).expect("run ok")
}

fn run_with_no_input(src: &str) -> Value {
    run_ok(src, "")
}

#[test]
fn entry_returns_literal() {
    let v = run_with_no_input("entry main() { return 42 }");
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 42.0));
}

#[test]
fn fn_invocation_adds() {
    let src = r#"
        fn add(a: Number, b: Number) -> Number { return a + b }
        entry main() { return add(2, 3) }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 5.0));
}

#[test]
fn arithmetic_precedence() {
    let v = run_with_no_input("entry main() { return 1 + 2 * 3 }");
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 7.0));
}

#[test]
fn if_else_branch() {
    let src = r#"
        fn sign(x: Number) -> Number {
            if x > 0 { return 1 } else { return 0 }
        }
        entry main() { return sign(5) }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 1.0));
}

#[test]
fn for_loop_sum() {
    let src = r#"
        entry main() {
            total = 0
            for x in [1, 2, 3, 4] {
                total = total + x
            }
            return total
        }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 10.0));
}

#[test]
fn list_indexing_via_get_sugar() {
    let src = r#"
        entry main() {
            xs = [10, 20, 30]
            return xs[1]
        }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 20.0));
}

#[test]
fn string_concat_and_length() {
    let src = r#"
        entry main() {
            s = "hello, " + "world"
            return length(s)
        }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 12.0));
}

#[test]
fn split_and_join_roundtrip() {
    let src = r#"
        entry main() {
            parts = split("a,b,c", ",")
            return join(parts, "-")
        }
    "#;
    let v = run_with_no_input(src);
    assert_eq!(v.as_text(), "a-b-c");
}

#[test]
fn membership_in_list() {
    let v = run_with_no_input("entry main() { return 2 in [1, 2, 3] }");
    assert!(matches!(v.kind, ValueKind::Bool(true)));
}

#[test]
fn membership_not_in_string() {
    let v = run_with_no_input(r#"entry main() { return "z" not in "hello" }"#);
    assert!(matches!(v.kind, ValueKind::Bool(true)));
}

#[test]
fn entry_uses_input_first_param() {
    let src = r#"
        entry main(text: Text) {
            return text + "!"
        }
    "#;
    let v = run_ok(src, "hi");
    assert_eq!(v.as_text(), "hi!");
}

#[test]
fn result_ok_unwrap() {
    let src = r#"
        entry main() {
            r = ok(7)
            return unwrap(r)
        }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 7.0));
}

#[test]
fn result_error_attempt_falls_through() {
    let src = r#"
        fn maybe_fail() -> Number { return error("nope") }
        fn fallback() -> Number { return 99 }
        entry main() {
            return attempt {
                try maybe_fail()
                try fallback()
            }
        }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 99.0));
}

#[test]
fn unwrap_or_default_on_error() {
    let src = r#"
        entry main() {
            r = error("boom")
            return unwrap_or(r, 42)
        }
    "#;
    let v = run_with_no_input(src);
    assert!(matches!(v.kind, ValueKind::Number(n) if n == 42.0));
}

#[test]
fn intent_without_adapter_errors() {
    let src = r#"
        intent classify(s: Text) -> Text { goal: classify s }
        entry main() {
            return classify("hi")
        }
    "#;
    let err = ail::run(src, "").expect_err("expected adapter error");
    let msg = format!("{err}");
    assert!(msg.contains("adapter") || msg.contains("intent"), "got: {msg}");
}

#[test]
fn boolean_short_circuit_or() {
    // If `or` short-circuits, undefined identifier `crash` (which would
    // be returned as a string symbol anyway, so this is mostly a sanity
    // check that the runtime doesn't blow up) is never evaluated.
    let v = run_with_no_input("entry main() { return true or crash }");
    assert!(matches!(v.kind, ValueKind::Bool(true)));
}

#[test]
fn confidence_min_propagates_through_list() {
    let v = run_with_no_input("entry main() { return [1, 2, 3] }");
    assert!((v.conf - 1.0).abs() < 1e-9);
}
