//! Behavioral tests for the AIL lexer. Mirrors the cases in
//! `go-impl/eval_test.go` lexer-relevant fragments and the Python
//! `reference-impl/tests/test_lexer*.py` set as Tekton lands them.

use ail::{Lexer, Tok};

fn kinds(src: &str) -> Vec<Tok> {
    Lexer::new(src)
        .tokenize()
        .expect("lex ok")
        .into_iter()
        .map(|t| t.kind)
        .collect()
}

#[test]
fn small_fn_program() {
    // fn add(a: Number, b: Number) -> Number { return a + b }
    let src = "fn add(a: Number, b: Number) -> Number { return a + b }";
    let expected = vec![
        Tok::Ident,  // fn
        Tok::Ident,  // add
        Tok::LParen,
        Tok::Ident,  // a
        Tok::Colon,
        Tok::Ident,  // Number
        Tok::Comma,
        Tok::Ident,  // b
        Tok::Colon,
        Tok::Ident,  // Number
        Tok::RParen,
        Tok::Arrow,
        Tok::Ident,  // Number
        Tok::LBrace,
        Tok::Ident,  // return
        Tok::Ident,  // a
        Tok::Plus,
        Tok::Ident,  // b
        Tok::RBrace,
        Tok::Eof,
    ];
    assert_eq!(kinds(src), expected);
}

#[test]
fn line_and_col_tracking() {
    let toks = Lexer::new("a\n  b").tokenize().unwrap();
    assert_eq!(toks[0].value, "a");
    assert_eq!((toks[0].line, toks[0].col), (1, 1));
    assert_eq!(toks[1].value, "b");
    assert_eq!((toks[1].line, toks[1].col), (2, 3));
}

#[test]
fn block_comment_skipped() {
    let src = "1 /* ignored\nstill ignored */ 2";
    assert_eq!(kinds(src), vec![Tok::Number, Tok::Number, Tok::Eof]);
}

#[test]
fn number_with_decimal() {
    let toks = Lexer::new("3.14").tokenize().unwrap();
    assert_eq!(toks[0].kind, Tok::Number);
    assert_eq!(toks[0].value, "3.14");
}

#[test]
fn string_with_escapes_value() {
    let toks = Lexer::new(r#""a\nb""#).tokenize().unwrap();
    assert_eq!(toks[0].kind, Tok::String);
    assert_eq!(toks[0].value, "a\nb");
}

#[test]
fn rejects_unknown_punct() {
    let err = Lexer::new("a @ b").tokenize().unwrap_err();
    assert!(err.msg.contains('@'));
}
