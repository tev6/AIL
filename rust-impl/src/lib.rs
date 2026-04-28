//! AIL (AI-Intent Language) — Rust runtime.
//!
//! Mirrors `go-impl/` and the Python `reference-impl/` against the spec at
//! `spec/08-reference-card.ai.md` (grammar v1.8). Phase-0 bootstrap: lexer only.

pub mod lexer;

pub use lexer::{LexError, Lexer, Tok, Token};
