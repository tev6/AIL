//! AIL (AI-Intent Language) — Rust runtime.
//!
//! Mirrors `go-impl/` and the Python `reference-impl/` against the spec at
//! `spec/08-reference-card.ai.md` (grammar v1.8). Phase-0 (lexer + parser +
//! evaluator) is complete; Phase-1 brings the Anthropic intent adapter.
//! Effects, evolve, and provenance remain owned by the Python reference.

pub mod anthropic;
pub mod ast;
pub mod eval;
pub mod lexer;
pub mod parser;
pub mod value;

pub use anthropic::AnthropicAdapter;
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
