//! AIL (AI-Intent Language) — Rust runtime.
//!
//! Mirrors `go-impl/` and the Python `reference-impl/` against the spec at
//! `spec/08-reference-card.ai.md` (grammar v1.8). Phase-0 bootstrap:
//! lexer + parser + evaluator. Effects, intent adapters, evolve, and
//! provenance remain owned by the Python reference for now.

pub mod ast;
pub mod eval;
pub mod lexer;
pub mod parser;
pub mod value;

pub use ast::{EntryDecl, Expr, FnDecl, IntentDecl, Literal, Param, Program, Stmt};
pub use eval::{Adapter, EvalError, EvalResult, Evaluator};
pub use lexer::{LexError, Lexer, Tok, Token};
pub use parser::{ParseError, Parser};
pub use value::{Value, ValueKind};

/// Convenience: lex + parse a source string into a `Program`.
pub fn parse(src: &str) -> Result<Program, Box<dyn std::error::Error>> {
    let tokens = Lexer::new(src).tokenize()?;
    let mut parser = Parser::new(tokens);
    Ok(parser.parse_program()?)
}

/// Convenience: lex + parse + evaluate without an adapter.
/// Returns the final `Value` (or whatever `entry` returns).
pub fn run(src: &str, input: &str) -> Result<Value, Box<dyn std::error::Error>> {
    let program = parse(src)?;
    let evaluator = Evaluator::new(&program);
    Ok(evaluator.run(input)?)
}
