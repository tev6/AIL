//! AIL lexer — port of `go-impl/lexer.go`.
//!
//! Token set is the language surface, not an implementation detail. Keep this
//! identical to `reference-impl/ail/parser/lexer.py` and `go-impl/lexer.go`.
//! Three runtimes diverging at the lexer is the spec being ambiguous.

use std::fmt;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tok {
    Eof,
    Ident,
    Number,
    String,
    LBrace,
    RBrace,
    LParen,
    RParen,
    LBrack,
    RBrack,
    Comma,
    Colon,
    Dot,
    Arrow,    // ->
    FatArrow, // =>
    Eq,       // =
    EqEq,     // ==
    Neq,      // !=
    Lt,
    Gt,
    Leq,
    Geq,
    Plus,
    Minus,
    Star,
    Slash,
    Percent,
}

impl fmt::Display for Tok {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            Tok::Eof => "EOF",
            Tok::Ident => "IDENT",
            Tok::Number => "NUMBER",
            Tok::String => "STRING",
            Tok::LBrace => "{",
            Tok::RBrace => "}",
            Tok::LParen => "(",
            Tok::RParen => ")",
            Tok::LBrack => "[",
            Tok::RBrack => "]",
            Tok::Comma => ",",
            Tok::Colon => ":",
            Tok::Dot => ".",
            Tok::Arrow => "->",
            Tok::FatArrow => "=>",
            Tok::Eq => "=",
            Tok::EqEq => "==",
            Tok::Neq => "!=",
            Tok::Lt => "<",
            Tok::Gt => ">",
            Tok::Leq => "<=",
            Tok::Geq => ">=",
            Tok::Plus => "+",
            Tok::Minus => "-",
            Tok::Star => "*",
            Tok::Slash => "/",
            Tok::Percent => "%",
        };
        f.write_str(s)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Token {
    pub kind: Tok,
    pub value: String,
    pub line: usize,
    pub col: usize,
}

impl fmt::Display for Token {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}({:?})@{}:{}", self.kind, self.value, self.line, self.col)
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LexError {
    pub line: usize,
    pub col: usize,
    pub msg: String,
}

impl fmt::Display for LexError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "lex error at {}:{}: {}", self.line, self.col, self.msg)
    }
}

impl std::error::Error for LexError {}

pub struct Lexer<'src> {
    src: &'src [u8],
    pos: usize,
    line: usize,
    col: usize,
}

impl<'src> Lexer<'src> {
    pub fn new(src: &'src str) -> Self {
        Self { src: src.as_bytes(), pos: 0, line: 1, col: 1 }
    }

    fn peek_at(&self, off: usize) -> u8 {
        let i = self.pos + off;
        if i >= self.src.len() { 0 } else { self.src[i] }
    }

    fn peek(&self) -> u8 { self.peek_at(0) }

    fn advance(&mut self) -> u8 {
        let ch = self.src[self.pos];
        self.pos += 1;
        if ch == b'\n' {
            self.line += 1;
            self.col = 1;
        } else {
            self.col += 1;
        }
        ch
    }

    /// Consume the entire source, returning the token stream terminated by `Tok::Eof`.
    /// Whitespace, `//` and `#` line comments, and `/* ... */` block comments are skipped.
    /// `#` is accepted as an alias for `//` — Python-trained AI authors reach for it
    /// reflexively; mirrors the tolerance in the Python and Go lexers.
    pub fn tokenize(mut self) -> Result<Vec<Token>, LexError> {
        let mut out = Vec::new();
        while self.pos < self.src.len() {
            let ch = self.peek();
            // whitespace
            if ch == b' ' || ch == b'\t' || ch == b'\r' || ch == b'\n' {
                self.advance();
                continue;
            }
            // // or # line comment
            if (ch == b'/' && self.peek_at(1) == b'/') || ch == b'#' {
                while self.pos < self.src.len() && self.peek() != b'\n' {
                    self.advance();
                }
                continue;
            }
            // /* block comment */
            if ch == b'/' && self.peek_at(1) == b'*' {
                self.advance();
                self.advance();
                while self.pos < self.src.len()
                    && !(self.peek() == b'*' && self.peek_at(1) == b'/')
                {
                    self.advance();
                }
                if self.pos < self.src.len() {
                    self.advance();
                    self.advance();
                }
                continue;
            }
            if ch == b'"' {
                out.push(self.lex_string()?);
                continue;
            }
            if ch.is_ascii_digit() {
                out.push(self.lex_number());
                continue;
            }
            if is_ident_start(ch) {
                out.push(self.lex_ident());
                continue;
            }
            out.push(self.lex_punct()?);
        }
        out.push(Token { kind: Tok::Eof, value: String::new(), line: self.line, col: self.col });
        Ok(out)
    }

    fn lex_string(&mut self) -> Result<Token, LexError> {
        let line = self.line;
        let col = self.col;
        self.advance(); // opening "
        let mut buf = Vec::new();
        while self.pos < self.src.len() && self.peek() != b'"' {
            let ch = self.advance();
            if ch == b'\\' && self.pos < self.src.len() {
                let nxt = self.advance();
                match nxt {
                    b'n' => buf.push(b'\n'),
                    b't' => buf.push(b'\t'),
                    b'r' => buf.push(b'\r'),
                    b'\\' => buf.push(b'\\'),
                    b'"' => buf.push(b'"'),
                    other => buf.push(other),
                }
            } else {
                buf.push(ch);
            }
        }
        if self.pos >= self.src.len() {
            return Err(LexError { line: self.line, col: self.col, msg: "unterminated string".into() });
        }
        self.advance(); // closing "
        let value = String::from_utf8(buf)
            .map_err(|e| LexError { line, col, msg: format!("invalid utf-8 in string: {e}") })?;
        Ok(Token { kind: Tok::String, value, line, col })
    }

    fn lex_number(&mut self) -> Token {
        let line = self.line;
        let col = self.col;
        let start = self.pos;
        while self.pos < self.src.len() && (self.peek().is_ascii_digit() || self.peek() == b'.') {
            self.advance();
        }
        let value = std::str::from_utf8(&self.src[start..self.pos]).unwrap_or("").to_string();
        Token { kind: Tok::Number, value, line, col }
    }

    fn lex_ident(&mut self) -> Token {
        let line = self.line;
        let col = self.col;
        let start = self.pos;
        while self.pos < self.src.len() && is_ident_continue(self.peek()) {
            self.advance();
        }
        let value = std::str::from_utf8(&self.src[start..self.pos]).unwrap_or("").to_string();
        Token { kind: Tok::Ident, value, line, col }
    }

    fn lex_punct(&mut self) -> Result<Token, LexError> {
        let line = self.line;
        let col = self.col;
        let ch = self.advance();
        let next = if self.pos < self.src.len() { self.peek() } else { 0 };
        let two_kind = match (ch, next) {
            (b'-', b'>') => Some(Tok::Arrow),
            (b'=', b'>') => Some(Tok::FatArrow),
            (b'=', b'=') => Some(Tok::EqEq),
            (b'!', b'=') => Some(Tok::Neq),
            (b'<', b'=') => Some(Tok::Leq),
            (b'>', b'=') => Some(Tok::Geq),
            _ => None,
        };
        if let Some(kind) = two_kind {
            self.advance();
            let value = format!("{}{}", ch as char, next as char);
            return Ok(Token { kind, value, line, col });
        }
        let kind = match ch {
            b'{' => Tok::LBrace,
            b'}' => Tok::RBrace,
            b'(' => Tok::LParen,
            b')' => Tok::RParen,
            b'[' => Tok::LBrack,
            b']' => Tok::RBrack,
            b',' => Tok::Comma,
            b':' => Tok::Colon,
            b'.' => Tok::Dot,
            b'=' => Tok::Eq,
            b'<' => Tok::Lt,
            b'>' => Tok::Gt,
            b'+' => Tok::Plus,
            b'-' => Tok::Minus,
            b'*' => Tok::Star,
            b'/' => Tok::Slash,
            b'%' => Tok::Percent,
            other => {
                return Err(LexError {
                    line,
                    col,
                    msg: format!("unexpected character {:?}", other as char),
                });
            }
        };
        Ok(Token { kind, value: (ch as char).to_string(), line, col })
    }
}

// Non-ASCII bytes (>= 0x80) are always part of a UTF-8 multi-byte
// sequence. Treating them as identifier characters lets the lexer pass
// through Korean, em-dashes, and other characters that show up in
// `goal:` prose blocks and natural-language string literals — matching
// Go's `unicode.IsLetter` behaviour. The resulting ident value remains
// valid UTF-8 because we only ever start consuming on a leading byte
// and stop on an ASCII boundary (whitespace, punctuation, EOF).
fn is_ident_start(ch: u8) -> bool {
    ch.is_ascii_alphabetic() || ch == b'_' || ch >= 0x80
}

fn is_ident_continue(ch: u8) -> bool {
    ch.is_ascii_alphanumeric() || ch == b'_' || ch >= 0x80
}

#[cfg(test)]
mod tests {
    use super::*;

    fn kinds(src: &str) -> Vec<Tok> {
        Lexer::new(src).tokenize().unwrap().into_iter().map(|t| t.kind).collect()
    }

    #[test]
    fn empty() {
        assert_eq!(kinds(""), vec![Tok::Eof]);
    }

    #[test]
    fn punctuation_two_char() {
        assert_eq!(
            kinds("-> => == != <= >="),
            vec![Tok::Arrow, Tok::FatArrow, Tok::EqEq, Tok::Neq, Tok::Leq, Tok::Geq, Tok::Eof],
        );
    }

    #[test]
    fn comment_alias_hash() {
        assert_eq!(kinds("# comment\n42"), vec![Tok::Number, Tok::Eof]);
    }

    #[test]
    fn string_escapes() {
        assert_eq!(kinds(r#""hello\n\t\"world\"""#), vec![Tok::String, Tok::Eof]);
    }

    #[test]
    fn unterminated_string_errors() {
        let err = Lexer::new("\"oops").tokenize().unwrap_err();
        assert!(err.msg.contains("unterminated"));
    }
}
