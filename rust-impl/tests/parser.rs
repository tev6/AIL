//! Behavioral tests for the AIL parser. Mirrors cases that would be
//! covered by `go-impl/eval_test.go` parse fragments and the Python
//! `reference-impl/tests/test_parser*.py` set as Tekton lands them.

use ail::ast::{Expr, Literal, Stmt};
use ail::{parse, Parser, Lexer};

fn parse_ok(src: &str) -> ail::Program {
    parse(src).expect("parse ok")
}

fn parse_err(src: &str) -> String {
    parse(src).err().expect("expected parse error").to_string()
}

#[test]
fn empty_program_no_entry() {
    let p = parse_ok("");
    assert!(p.fns.is_empty());
    assert!(p.intents.is_empty());
    assert!(p.entry.is_none());
}

#[test]
fn simple_fn_add() {
    let p = parse_ok("fn add(a: Number, b: Number) -> Number { return a + b }");
    let f = p.fns.get("add").expect("add fn");
    assert_eq!(f.params.len(), 2);
    assert_eq!(f.params[0].name, "a");
    assert_eq!(f.params[0].type_name, "Number");
    assert_eq!(f.return_type, "Number");
    assert_eq!(f.body.len(), 1);
    match &f.body[0] {
        Stmt::Return(Some(Expr::Binary { op, .. })) => assert_eq!(op.as_str(), "+"),
        other => panic!("unexpected stmt: {other:?}"),
    }
}

#[test]
fn entry_with_assign_and_call() {
    let src = r#"
        fn greet(name: Text) -> Text { return name }
        entry main() {
            x = greet("world")
            return x
        }
    "#;
    let p = parse_ok(src);
    assert!(p.entry.is_some(), "entry parsed");
    assert!(p.fns.contains_key("greet"));
    let entry = p.entry.unwrap();
    assert_eq!(entry.name, "main");
    assert_eq!(entry.body.len(), 2);
    match &entry.body[0] {
        Stmt::Assign { name, value } => {
            assert_eq!(name, "x");
            assert!(matches!(value, Expr::Call { .. }));
        }
        other => panic!("expected assign, got {other:?}"),
    }
}

#[test]
fn pure_fn_parses() {
    // pure fn is parsed but the static purity contract is owned by Python.
    let p = parse_ok("pure fn id(x: Number) -> Number { return x }");
    assert!(p.fns.contains_key("id"));
}

#[test]
fn import_skipped() {
    let p = parse_ok(r#"import core from "stdlib/core""#);
    assert!(p.fns.is_empty());
    assert!(p.entry.is_none());
}

#[test]
fn parametric_type_swallowed() {
    let p = parse_ok("fn first(xs: List[Number]) -> Number { return xs[0] }");
    assert_eq!(p.fns["first"].params[0].type_name, "List");
}

#[test]
fn precedence_add_mul() {
    let src = "fn r() -> Number { return 1 + 2 * 3 }";
    let p = parse_ok(src);
    let body = &p.fns["r"].body;
    match &body[0] {
        Stmt::Return(Some(Expr::Binary { op, left, right })) => {
            assert_eq!(op.as_str(), "+");
            assert!(matches!(left.as_ref(), Expr::Literal(Literal::Number(_))));
            assert!(matches!(right.as_ref(), Expr::Binary { op, .. } if op.as_str() == "*"));
        }
        other => panic!("unexpected: {other:?}"),
    }
}

#[test]
fn membership_in_and_not_in() {
    let p = parse_ok(r#"fn r() -> Boolean { return 1 not in [2, 3] }"#);
    let body = &p.fns["r"].body;
    match &body[0] {
        Stmt::Return(Some(Expr::Membership { negated, .. })) => {
            assert!(*negated, "negated = true");
        }
        other => panic!("expected Membership, got {other:?}"),
    }
}

#[test]
fn index_sugars_to_get_call() {
    let p = parse_ok("fn r() -> Number { return xs[0] }");
    let body = &p.fns["r"].body;
    match &body[0] {
        Stmt::Return(Some(Expr::Call { callee, args })) => {
            assert!(matches!(callee.as_ref(), Expr::Ident(n) if n.as_str() == "get"));
            assert_eq!(args.len(), 2);
        }
        other => panic!("expected get(...) call, got {other:?}"),
    }
}

#[test]
fn if_else_branch() {
    let src = r#"
        fn r(x: Number) -> Number {
            if x > 0 {
                return 1
            } else {
                return 0
            }
        }
    "#;
    let p = parse_ok(src);
    match &p.fns["r"].body[0] {
        Stmt::If { then_body, else_body, .. } => {
            assert_eq!(then_body.len(), 1);
            assert_eq!(else_body.len(), 1);
        }
        other => panic!("expected if, got {other:?}"),
    }
}

#[test]
fn for_loop() {
    let src = r#"
        fn r() -> Number {
            for x in [1, 2, 3] {
                x = x
            }
            return 0
        }
    "#;
    let p = parse_ok(src);
    match &p.fns["r"].body[0] {
        Stmt::For { var, body, .. } => {
            assert_eq!(var, "x");
            assert_eq!(body.len(), 1);
        }
        other => panic!("expected for, got {other:?}"),
    }
}

#[test]
fn attempt_block_with_tries() {
    let src = r#"
        fn r() -> Number {
            return attempt {
                try fast()
                try slow()
            }
        }
    "#;
    let p = parse_ok(src);
    match &p.fns["r"].body[0] {
        Stmt::Return(Some(Expr::Attempt(tries))) => {
            assert_eq!(tries.len(), 2);
        }
        other => panic!("expected attempt, got {other:?}"),
    }
}

#[test]
fn attempt_requires_try() {
    let err = parse_err(r#"fn r() -> Number { return attempt { fast() } }"#);
    assert!(err.contains("`try`"), "got: {err}");
}

#[test]
fn intent_parses_goal_and_constraints() {
    let src = r#"
        intent classify(x: Text) -> Text {
            goal: decide whether x is spam
            constraints {
                short
                lowercase
            }
        }
    "#;
    let p = parse_ok(src);
    let it = p.intents.get("classify").expect("classify intent");
    assert!(it.goal.contains("spam"), "goal: {:?}", it.goal);
    assert_eq!(it.constraints.len(), 2);
}

#[test]
fn unknown_top_level_keyword_errors() {
    let err = parse_err("widget foo()");
    assert!(err.contains("widget"), "got: {err}");
}

#[test]
fn unterminated_brace_errors() {
    let err = parse_err("fn r() -> Number { return 1");
    assert!(err.contains("expected") || err.contains("}"), "got: {err}");
}

// Re-export checker — proves the `parse` helper and `Lexer`/`Parser`
// types are public and composable.
#[test]
fn lexer_parser_pipeline_compiles() {
    let toks = Lexer::new("entry main() { return 1 }").tokenize().unwrap();
    let mut p = Parser::new(toks);
    let _ = p.parse_program().unwrap();
}
