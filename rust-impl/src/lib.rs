//! AIL (AI-Intent Language) — Rust runtime.
//!
//! Mirrors `go-impl/` and the Python `reference-impl/` against the spec at
//! `spec/08-reference-card.ai.md` (grammar v1.8). Phase-0 bootstrap:
//! lexer + parser. Evaluator next.

pub mod ast;
pub mod lexer;
pub mod parser;

pub use ast::{EntryDecl, Expr, FnDecl, IntentDecl, Literal, Param, Program, Stmt};
pub use lexer::{LexError, Lexer, Tok, Token};
pub use parser::{ParseError, Parser};

/// Convenience: lex + parse a source string into a `Program`.
pub fn parse(src: &str) -> Result<Program, Box<dyn std::error::Error>> {
    let tokens = Lexer::new(src).tokenize()?;
    let mut parser = Parser::new(tokens);
    Ok(parser.parse_program()?)
}
