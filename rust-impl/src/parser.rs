//! AIL recursive-descent parser — port of `go-impl/parser.go`.
//!
//! Subset matches the Go runtime (Phase-0):
//!   fn / intent / entry, assign / return / if / for / expr-stmt,
//!   literals / ident / field / call / list / paren / membership /
//!   binary / unary / attempt.
//!
//! Not yet supported (parse error): context, evolve, effect, perform,
//! branch, with. The Python reference owns the static guarantees;
//! `pure fn` parses but is treated like `fn`.

use std::fmt;

use crate::ast::{EntryDecl, Expr, FnDecl, IntentDecl, Literal, Param, Program, Stmt};
use crate::lexer::{Tok, Token};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ParseError {
    pub msg: String,
    pub line: usize,
    pub col: usize,
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "parse error at {}:{}: {}", self.line, self.col, self.msg)
    }
}

impl std::error::Error for ParseError {}

pub struct Parser {
    tokens: Vec<Token>,
    i: usize,
}

impl Parser {
    pub fn new(tokens: Vec<Token>) -> Self {
        Self { tokens, i: 0 }
    }

    pub fn parse_program(&mut self) -> Result<Program, ParseError> {
        let mut prog = Program::new();
        while !self.check(Tok::Eof) {
            self.parse_top_level(&mut prog)?;
        }
        Ok(prog)
    }

    // ---------------- helpers ----------------

    fn peek_at(&self, off: usize) -> &Token {
        &self.tokens[self.i + off]
    }

    fn peek(&self) -> &Token {
        self.peek_at(0)
    }

    fn advance(&mut self) -> Token {
        let t = self.tokens[self.i].clone();
        self.i += 1;
        t
    }

    fn check(&self, kind: Tok) -> bool {
        self.peek().kind == kind
    }

    fn check_kw(&self, kw: &str) -> bool {
        let t = self.peek();
        t.kind == Tok::Ident && t.value == kw
    }

    fn match_tok(&mut self, kind: Tok) -> bool {
        if self.check(kind) {
            self.advance();
            true
        } else {
            false
        }
    }

    fn match_kw(&mut self, kw: &str) -> bool {
        if self.check_kw(kw) {
            self.advance();
            true
        } else {
            false
        }
    }

    fn expect(&mut self, kind: Tok) -> Result<Token, ParseError> {
        if !self.check(kind) {
            let t = self.peek();
            return Err(ParseError {
                msg: format!("expected {}, got {}({:?})", kind, t.kind, t.value),
                line: t.line,
                col: t.col,
            });
        }
        Ok(self.advance())
    }

    fn expect_kw(&mut self, kw: &str) -> Result<(), ParseError> {
        if !self.check_kw(kw) {
            let t = self.peek();
            return Err(ParseError {
                msg: format!("expected {:?}, got {}({:?})", kw, t.kind, t.value),
                line: t.line,
                col: t.col,
            });
        }
        self.advance();
        Ok(())
    }

    // ---------------- top level ----------------

    fn parse_top_level(&mut self, prog: &mut Program) -> Result<(), ParseError> {
        let t = self.peek().clone();
        if t.kind != Tok::Ident {
            return Err(ParseError {
                msg: format!("unexpected top-level token {}", t.kind),
                line: t.line,
                col: t.col,
            });
        }
        // `pure fn` accepted for syntax compat — Rust runtime doesn't enforce
        // the purity check; the Python reference owns static guarantees.
        if t.value == "pure"
            && self.peek_at(1).kind == Tok::Ident
            && self.peek_at(1).value == "fn"
        {
            self.advance(); // consume `pure`
            let fn_decl = self.parse_fn()?;
            prog.fns.insert(fn_decl.name.clone(), fn_decl);
            return Ok(());
        }
        match t.value.as_str() {
            "fn" => {
                let fn_decl = self.parse_fn()?;
                prog.fns.insert(fn_decl.name.clone(), fn_decl);
            }
            "intent" => {
                let it = self.parse_intent()?;
                prog.intents.insert(it.name.clone(), it);
            }
            "entry" => {
                let en = self.parse_entry()?;
                prog.entry = Some(en);
            }
            "import" => {
                // v0: skip the declaration shape — stdlib not re-implemented.
                // syntax: `import NAME from "source"`
                self.advance();
                self.expect(Tok::Ident)?;
                self.expect_kw("from")?;
                self.expect(Tok::String)?;
            }
            other => {
                return Err(ParseError {
                    msg: format!("unexpected top-level keyword {:?}", other),
                    line: t.line,
                    col: t.col,
                });
            }
        }
        Ok(())
    }

    fn parse_params(&mut self) -> Result<Vec<Param>, ParseError> {
        self.expect(Tok::LParen)?;
        let mut params = Vec::new();
        if !self.check(Tok::RParen) {
            loop {
                let name = self.expect(Tok::Ident)?;
                let mut type_name = String::new();
                if self.match_tok(Tok::Colon) {
                    type_name = self.parse_type_name()?;
                }
                params.push(Param { name: name.value, type_name });
                if !self.match_tok(Tok::Comma) {
                    break;
                }
            }
        }
        self.expect(Tok::RParen)?;
        Ok(params)
    }

    /// Parses parametric types like `List[Number]`, `Map[Text, Number]`,
    /// `Result[Text]`. Inner types are consumed and discarded — AIL is
    /// dynamically typed at runtime — but the model's preferred shape
    /// parses cleanly. Must stay in lockstep with the Python parser.
    fn parse_type_name(&mut self) -> Result<String, ParseError> {
        let t = self.expect(Tok::Ident)?;
        if self.peek().kind == Tok::LBrack {
            self.advance();
            let mut depth = 1;
            while depth > 0 && self.peek().kind != Tok::Eof {
                let k = self.peek().kind;
                self.advance();
                if k == Tok::LBrack {
                    depth += 1;
                } else if k == Tok::RBrack {
                    depth -= 1;
                }
            }
        }
        Ok(t.value)
    }

    fn parse_fn(&mut self) -> Result<FnDecl, ParseError> {
        self.expect_kw("fn")?;
        let name = self.expect(Tok::Ident)?;
        let params = self.parse_params()?;
        let mut return_type = String::new();
        if self.match_tok(Tok::Arrow) {
            return_type = self.parse_type_name()?;
        }
        self.expect(Tok::LBrace)?;
        let body = self.parse_block()?;
        self.expect(Tok::RBrace)?;
        Ok(FnDecl { name: name.value, params, return_type, body })
    }

    fn parse_intent(&mut self) -> Result<IntentDecl, ParseError> {
        self.expect_kw("intent")?;
        let name = self.expect(Tok::Ident)?;
        let params = self.parse_params()?;
        let mut return_type = String::new();
        if self.match_tok(Tok::Arrow) {
            return_type = self.parse_type_name()?;
        }
        self.expect(Tok::LBrace)?;
        let mut it = IntentDecl {
            name: name.value,
            params,
            return_type,
            goal: String::new(),
            constraints: Vec::new(),
        };
        while !self.check(Tok::RBrace) {
            if self.check_kw("goal") {
                self.advance();
                self.expect(Tok::Colon)?;
                // Goal is free-form prose up to the next field-terminator or brace.
                let mut buf = String::new();
                while !self.check(Tok::RBrace)
                    && !self.check_kw("constraints")
                    && !self.check_kw("examples")
                    && !self.check_kw("on_low_confidence")
                    && !self.check_kw("trace")
                {
                    if !buf.is_empty() {
                        buf.push(' ');
                    }
                    let tok = self.advance();
                    buf.push_str(&tok.value);
                }
                it.goal = buf.trim().to_string();
            } else if self.check_kw("constraints") {
                self.advance();
                self.expect(Tok::LBrace)?;
                while !self.check(Tok::RBrace) {
                    let mut buf = String::new();
                    // consume identifier-run; treat each run as one constraint.
                    while !self.check(Tok::RBrace) {
                        let kind = self.peek().kind;
                        if kind == Tok::Ident {
                            if !buf.is_empty() {
                                break;
                            }
                            buf.push_str(&self.advance().value);
                        } else {
                            break;
                        }
                    }
                    if buf.is_empty() {
                        self.advance(); // skip unknown token
                    } else {
                        it.constraints.push(buf);
                    }
                }
                self.expect(Tok::RBrace)?;
            } else {
                // Skip unknown intent field for v0
                self.advance();
            }
        }
        self.expect(Tok::RBrace)?;
        Ok(it)
    }

    fn parse_entry(&mut self) -> Result<EntryDecl, ParseError> {
        self.expect_kw("entry")?;
        let name = self.expect(Tok::Ident)?;
        let params = self.parse_params()?;
        self.expect(Tok::LBrace)?;
        let body = self.parse_block()?;
        self.expect(Tok::RBrace)?;
        Ok(EntryDecl { name: name.value, params, body })
    }

    // ---------------- statements ----------------

    fn parse_block(&mut self) -> Result<Vec<Stmt>, ParseError> {
        let mut out = Vec::new();
        while !self.check(Tok::RBrace) && !self.check(Tok::Eof) {
            out.push(self.parse_stmt()?);
        }
        Ok(out)
    }

    fn parse_stmt(&mut self) -> Result<Stmt, ParseError> {
        let t = self.peek().clone();
        if t.kind == Tok::Ident {
            match t.value.as_str() {
                "return" => {
                    self.advance();
                    if self.check(Tok::RBrace) {
                        return Ok(Stmt::Return(None));
                    }
                    let e = self.parse_expr()?;
                    return Ok(Stmt::Return(Some(e)));
                }
                "if" => return self.parse_if(),
                "for" => return self.parse_for(),
                _ => {}
            }
            // lookahead for assignment: IDENT '=' ...  (not '==')
            if self.peek_at(1).kind == Tok::Eq {
                let name = self.advance().value;
                self.advance(); // '='
                let val = self.parse_expr()?;
                return Ok(Stmt::Assign { name, value: val });
            }
        }
        let e = self.parse_expr()?;
        Ok(Stmt::Expr(e))
    }

    fn parse_if(&mut self) -> Result<Stmt, ParseError> {
        self.expect_kw("if")?;
        let cond = self.parse_expr()?;
        self.expect(Tok::LBrace)?;
        let then_body = self.parse_block()?;
        self.expect(Tok::RBrace)?;
        let mut else_body = Vec::new();
        if self.match_kw("else") {
            if self.check_kw("if") {
                let nested = self.parse_if()?;
                else_body = vec![nested];
            } else {
                self.expect(Tok::LBrace)?;
                else_body = self.parse_block()?;
                self.expect(Tok::RBrace)?;
            }
        }
        Ok(Stmt::If { cond, then_body, else_body })
    }

    fn parse_for(&mut self) -> Result<Stmt, ParseError> {
        self.expect_kw("for")?;
        let name = self.expect(Tok::Ident)?;
        self.expect_kw("in")?;
        let coll = self.parse_expr()?;
        self.expect(Tok::LBrace)?;
        let body = self.parse_block()?;
        self.expect(Tok::RBrace)?;
        Ok(Stmt::For { var: name.value, coll, body })
    }

    // ---------------- expressions ----------------
    //
    // Precedence (low to high):
    //   or
    //   and
    //   == != in not-in
    //   < <= > >=
    //   + -
    //   * / %
    //   unary (- not)
    //   primary (literal, ident, call, list, paren, attempt)

    pub fn parse_expr(&mut self) -> Result<Expr, ParseError> {
        self.parse_or()
    }

    fn parse_or(&mut self) -> Result<Expr, ParseError> {
        let mut left = self.parse_and()?;
        while self.match_kw("or") {
            let right = self.parse_and()?;
            left = Expr::Binary { op: "or".into(), left: Box::new(left), right: Box::new(right) };
        }
        Ok(left)
    }

    fn parse_and(&mut self) -> Result<Expr, ParseError> {
        let mut left = self.parse_eq()?;
        while self.match_kw("and") {
            let right = self.parse_eq()?;
            left = Expr::Binary { op: "and".into(), left: Box::new(left), right: Box::new(right) };
        }
        Ok(left)
    }

    fn parse_eq(&mut self) -> Result<Expr, ParseError> {
        let mut left = self.parse_rel()?;
        loop {
            if self.check_kw("in") {
                self.advance();
                let right = self.parse_rel()?;
                left = Expr::Membership {
                    element: Box::new(left),
                    collection: Box::new(right),
                    negated: false,
                };
                continue;
            }
            if self.check_kw("not")
                && self.peek_at(1).kind == Tok::Ident
                && self.peek_at(1).value == "in"
            {
                self.advance();
                self.advance();
                let right = self.parse_rel()?;
                left = Expr::Membership {
                    element: Box::new(left),
                    collection: Box::new(right),
                    negated: true,
                };
                continue;
            }
            if self.match_tok(Tok::EqEq) {
                let right = self.parse_rel()?;
                left = Expr::Binary { op: "==".into(), left: Box::new(left), right: Box::new(right) };
                continue;
            }
            if self.match_tok(Tok::Neq) {
                let right = self.parse_rel()?;
                left = Expr::Binary { op: "!=".into(), left: Box::new(left), right: Box::new(right) };
                continue;
            }
            return Ok(left);
        }
    }

    fn parse_rel(&mut self) -> Result<Expr, ParseError> {
        let mut left = self.parse_add()?;
        loop {
            let op = if self.match_tok(Tok::Lt) {
                "<"
            } else if self.match_tok(Tok::Gt) {
                ">"
            } else if self.match_tok(Tok::Leq) {
                "<="
            } else if self.match_tok(Tok::Geq) {
                ">="
            } else {
                return Ok(left);
            };
            let right = self.parse_add()?;
            left = Expr::Binary { op: op.into(), left: Box::new(left), right: Box::new(right) };
        }
    }

    fn parse_add(&mut self) -> Result<Expr, ParseError> {
        let mut left = self.parse_mul()?;
        loop {
            let op = if self.match_tok(Tok::Plus) {
                "+"
            } else if self.match_tok(Tok::Minus) {
                "-"
            } else {
                return Ok(left);
            };
            let right = self.parse_mul()?;
            left = Expr::Binary { op: op.into(), left: Box::new(left), right: Box::new(right) };
        }
    }

    fn parse_mul(&mut self) -> Result<Expr, ParseError> {
        let mut left = self.parse_unary()?;
        loop {
            let op = if self.match_tok(Tok::Star) {
                "*"
            } else if self.match_tok(Tok::Slash) {
                "/"
            } else if self.match_tok(Tok::Percent) {
                "%"
            } else {
                return Ok(left);
            };
            let right = self.parse_unary()?;
            left = Expr::Binary { op: op.into(), left: Box::new(left), right: Box::new(right) };
        }
    }

    fn parse_unary(&mut self) -> Result<Expr, ParseError> {
        if self.match_kw("not") {
            let operand = self.parse_unary()?;
            return Ok(Expr::Unary { op: "not".into(), operand: Box::new(operand) });
        }
        if self.match_tok(Tok::Minus) {
            let operand = self.parse_unary()?;
            return Ok(Expr::Unary { op: "-".into(), operand: Box::new(operand) });
        }
        self.parse_postfix()
    }

    fn parse_postfix(&mut self) -> Result<Expr, ParseError> {
        let mut e = self.parse_primary()?;
        loop {
            if self.match_tok(Tok::Dot) {
                let field = self.expect(Tok::Ident)?;
                e = Expr::FieldAccess { target: Box::new(e), field: field.value };
                continue;
            }
            if self.match_tok(Tok::LParen) {
                let mut args = Vec::new();
                if !self.check(Tok::RParen) {
                    loop {
                        args.push(self.parse_expr()?);
                        if !self.match_tok(Tok::Comma) {
                            break;
                        }
                    }
                }
                self.expect(Tok::RParen)?;
                e = Expr::Call { callee: Box::new(e), args };
                continue;
            }
            if self.match_tok(Tok::LBrack) {
                // `target[index]` is parser-only sugar for `get(target, index)`.
                let idx = self.parse_expr()?;
                self.expect(Tok::RBrack)?;
                e = Expr::Call {
                    callee: Box::new(Expr::Ident("get".into())),
                    args: vec![e, idx],
                };
                continue;
            }
            return Ok(e);
        }
    }

    fn parse_primary(&mut self) -> Result<Expr, ParseError> {
        let t = self.peek().clone();
        match t.kind {
            Tok::String => {
                self.advance();
                Ok(Expr::Literal(Literal::Text(t.value)))
            }
            Tok::Number => {
                self.advance();
                let f: f64 = t.value.parse().map_err(|_| ParseError {
                    msg: format!("bad number {:?}", t.value),
                    line: t.line,
                    col: t.col,
                })?;
                Ok(Expr::Literal(Literal::Number(f)))
            }
            Tok::LBrack => {
                self.advance();
                let mut items = Vec::new();
                if !self.check(Tok::RBrack) {
                    loop {
                        items.push(self.parse_expr()?);
                        if !self.match_tok(Tok::Comma) {
                            break;
                        }
                    }
                }
                self.expect(Tok::RBrack)?;
                Ok(Expr::List(items))
            }
            Tok::LParen => {
                self.advance();
                let e = self.parse_expr()?;
                self.expect(Tok::RParen)?;
                Ok(e)
            }
            Tok::Minus => {
                self.advance();
                let operand = self.parse_unary()?;
                Ok(Expr::Unary { op: "-".into(), operand: Box::new(operand) })
            }
            Tok::Ident => {
                self.advance();
                match t.value.as_str() {
                    "true" => Ok(Expr::Literal(Literal::Bool(true))),
                    "false" => Ok(Expr::Literal(Literal::Bool(false))),
                    "attempt" => self.parse_attempt(),
                    _ => Ok(Expr::Ident(t.value)),
                }
            }
            _ => Err(ParseError {
                msg: format!("unexpected token {}({:?})", t.kind, t.value),
                line: t.line,
                col: t.col,
            }),
        }
    }

    /// `attempt { try EXPR ... }`. Leading `attempt` ident already consumed.
    fn parse_attempt(&mut self) -> Result<Expr, ParseError> {
        self.expect(Tok::LBrace)?;
        let mut tries = Vec::new();
        while !self.check(Tok::RBrace) {
            if !self.check_kw("try") {
                let t = self.peek();
                return Err(ParseError {
                    msg: format!(
                        "expected `try` inside attempt block, got {}({:?})",
                        t.kind, t.value
                    ),
                    line: t.line,
                    col: t.col,
                });
            }
            self.advance();
            tries.push(self.parse_expr()?);
        }
        self.expect(Tok::RBrace)?;
        if tries.is_empty() {
            let t = self.peek();
            return Err(ParseError {
                msg: "attempt block must contain at least one `try`".into(),
                line: t.line,
                col: t.col,
            });
        }
        Ok(Expr::Attempt(tries))
    }
}
