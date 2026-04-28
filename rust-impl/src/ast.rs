//! AIL AST — port of `go-impl/ast.go`.
//!
//! Go uses interfaces (`exprNode()`, `stmtNode()`) as sum types; Rust uses
//! enums. The shape and semantics match — keep them identical so the spec
//! stays single-sourced. Names mirror the Go nodes (e.g. `Expr::Literal`
//! is `LiteralExpr`).

#[derive(Debug, Clone, PartialEq)]
pub enum Literal {
    Number(f64),
    Text(String),
    Bool(bool),
}

#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    Literal(Literal),
    Ident(String),
    FieldAccess { target: Box<Expr>, field: String },
    Call { callee: Box<Expr>, args: Vec<Expr> },
    Binary { op: String, left: Box<Expr>, right: Box<Expr> },
    Unary { op: String, operand: Box<Expr> },
    List(Vec<Expr>),
    /// `element in collection` / `element not in collection`
    Membership { element: Box<Expr>, collection: Box<Expr>, negated: bool },
    /// `attempt { try EXPR try EXPR ... }` — confidence-priority cascade.
    /// Walk `tries` in order, return the first non-error Result-wrapped value.
    /// If all tries are errors, the last is returned.
    Attempt(Vec<Expr>),
}

#[derive(Debug, Clone, PartialEq)]
pub enum Stmt {
    Assign { name: String, value: Expr },
    /// `return` with no expression yields `None` here.
    Return(Option<Expr>),
    If { cond: Expr, then_body: Vec<Stmt>, else_body: Vec<Stmt> },
    For { var: String, coll: Expr, body: Vec<Stmt> },
    Expr(Expr),
}

#[derive(Debug, Clone, PartialEq)]
pub struct Param {
    pub name: String,
    pub type_name: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct FnDecl {
    pub name: String,
    pub params: Vec<Param>,
    pub return_type: String,
    pub body: Vec<Stmt>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct IntentDecl {
    pub name: String,
    pub params: Vec<Param>,
    pub return_type: String,
    /// Free-form prose captured as a single string.
    pub goal: String,
    /// Each constraint is one identifier-run (subset matching go-impl v0).
    pub constraints: Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct EntryDecl {
    pub name: String,
    pub params: Vec<Param>,
    pub body: Vec<Stmt>,
}

#[derive(Debug, Clone, Default)]
pub struct Program {
    pub fns: std::collections::BTreeMap<String, FnDecl>,
    pub intents: std::collections::BTreeMap<String, IntentDecl>,
    pub entry: Option<EntryDecl>,
}

impl Program {
    pub fn new() -> Self {
        Self::default()
    }
}
