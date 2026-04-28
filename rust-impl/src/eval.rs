//! AIL evaluator — port of `go-impl/eval.go`.
//!
//! Phase-0 subset: fn dispatch, builtins (string/list/math/Result),
//! arithmetic, comparisons, membership, attempt cascade. `intent`
//! requires an adapter; without one, calling an intent errors. Spec
//! parity with the Python reference is the goal — confidence
//! propagates as `min(child confidences)` and Result envelopes share
//! the `{_result, ok, value|error}` shape.

use std::collections::BTreeMap;
use std::fmt;

use crate::ast::{Expr, FnDecl, IntentDecl, Literal, Program, Stmt};
use crate::value::{make_error, make_ok, min_conf, Value, ValueKind};

#[derive(Debug)]
pub enum EvalError {
    /// `return EXPR` propagates as `Err(Return(v))` and is caught at the
    /// fn boundary. Mirrors Go's `returnSig` / Python's `_ReturnSignal`.
    Return(Value),
    Msg(String),
}

impl fmt::Display for EvalError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EvalError::Return(_) => f.write_str("<return signal>"),
            EvalError::Msg(s) => f.write_str(s),
        }
    }
}

impl std::error::Error for EvalError {}

impl EvalError {
    pub fn msg<S: Into<String>>(s: S) -> Self {
        EvalError::Msg(s.into())
    }
}

pub type EvalResult = Result<Value, EvalError>;

/// `intent` dispatcher — supplies an external implementation (typically
/// an LLM client). The Phase-0 Rust runtime ships without an adapter;
/// invoking an `intent` declaration errors out unless one is plugged in.
pub trait Adapter {
    fn invoke(
        &self,
        goal: &str,
        constraints: &[String],
        inputs: &BTreeMap<String, Value>,
    ) -> EvalResult;
}

pub struct Evaluator<'p> {
    pub program: &'p Program,
    pub adapter: Option<Box<dyn Adapter>>,
}

impl<'p> Evaluator<'p> {
    pub fn new(program: &'p Program) -> Self {
        Self { program, adapter: None }
    }

    pub fn with_adapter(program: &'p Program, adapter: Box<dyn Adapter>) -> Self {
        Self { program, adapter: Some(adapter) }
    }

    pub fn run(&self, input: &str) -> EvalResult {
        let entry = self
            .program
            .entry
            .as_ref()
            .ok_or_else(|| EvalError::msg("program has no entry declaration"))?;
        let mut scope: BTreeMap<String, Value> = BTreeMap::new();
        for (i, p) in entry.params.iter().enumerate() {
            if i == 0 {
                scope.insert(p.name.clone(), Value::text(input));
            } else {
                scope.insert(p.name.clone(), Value::null());
            }
        }
        match self.exec_block(&entry.body, &mut scope) {
            Ok(v) => Ok(v),
            Err(EvalError::Return(v)) => Ok(v),
            Err(e) => Err(e),
        }
    }

    fn exec_block(
        &self,
        stmts: &[Stmt],
        scope: &mut BTreeMap<String, Value>,
    ) -> EvalResult {
        let mut last = Value::null();
        for s in stmts {
            last = self.exec_stmt(s, scope)?;
        }
        Ok(last)
    }

    fn exec_stmt(&self, s: &Stmt, scope: &mut BTreeMap<String, Value>) -> EvalResult {
        match s {
            Stmt::Assign { name, value } => {
                let v = self.eval_expr(value, scope)?;
                scope.insert(name.clone(), v.clone());
                Ok(v)
            }
            Stmt::Return(opt) => {
                let v = match opt {
                    Some(e) => self.eval_expr(e, scope)?,
                    None => Value::null(),
                };
                Err(EvalError::Return(v))
            }
            Stmt::If { cond, then_body, else_body } => {
                let c = self.eval_expr(cond, scope)?;
                if c.truthy() {
                    self.exec_block(then_body, scope)
                } else {
                    self.exec_block(else_body, scope)
                }
            }
            Stmt::For { var, coll, body } => {
                let coll_v = self.eval_expr(coll, scope)?;
                let items = match coll_v.kind {
                    ValueKind::List(xs) => xs,
                    _ => return Err(EvalError::msg("for: collection is not a list")),
                };
                for it in items {
                    scope.insert(var.clone(), it);
                    self.exec_block(body, scope)?;
                }
                Ok(Value::null())
            }
            Stmt::Expr(e) => self.eval_expr(e, scope),
        }
    }

    fn eval_expr(&self, expr: &Expr, scope: &mut BTreeMap<String, Value>) -> EvalResult {
        match expr {
            Expr::Literal(lit) => Ok(match lit {
                Literal::Number(n) => Value::number(*n),
                Literal::Text(s) => Value::text(s.clone()),
                Literal::Bool(b) => Value::bool_val(*b),
            }),
            Expr::Ident(name) => {
                if let Some(v) = scope.get(name) {
                    Ok(v.clone())
                } else {
                    // Bare identifier becomes a string symbol — matches Python
                    // behavior for constraint labels like `positive_negative_neutral`.
                    Ok(Value::text(name.clone()))
                }
            }
            Expr::List(items) => {
                let mut out = Vec::with_capacity(items.len());
                let mut minc = 1.0f64;
                for it in items {
                    let v = self.eval_expr(it, scope)?;
                    if v.conf < minc {
                        minc = v.conf;
                    }
                    out.push(v);
                }
                Ok(Value::list(out).with_conf(minc))
            }
            Expr::Binary { op, left, right } => self.eval_binary(op, left, right, scope),
            Expr::Unary { op, operand } => {
                let v = self.eval_expr(operand, scope)?;
                match op.as_str() {
                    "not" => Ok(Value::bool_val(!v.truthy()).with_conf(v.conf)),
                    "-" => match v.kind {
                        ValueKind::Number(n) => Ok(Value::number(-n).with_conf(v.conf)),
                        _ => Err(EvalError::msg("unary -: operand is not a number")),
                    },
                    other => Err(EvalError::msg(format!("unknown unary op {:?}", other))),
                }
            }
            Expr::Call { callee, args } => self.eval_call(callee, args, scope),
            Expr::Attempt(tries) => self.eval_attempt(tries, scope),
            Expr::Membership { element, collection, negated } => {
                let elem = self.eval_expr(element, scope)?;
                let coll = self.eval_expr(collection, scope)?;
                let mut contained = contains_value(&coll.kind, &elem.kind);
                if *negated {
                    contained = !contained;
                }
                Ok(Value::bool_val(contained).with_conf(min_conf(elem.conf, coll.conf)))
            }
            Expr::FieldAccess { target, field } => {
                let t = self.eval_expr(target, scope)?;
                match t.kind {
                    ValueKind::Record(m) => {
                        if let Some(v) = m.get(field) {
                            Ok(v.clone())
                        } else {
                            Ok(Value::null().with_conf(t.conf))
                        }
                    }
                    _ => Err(EvalError::msg("field access on non-record")),
                }
            }
        }
    }

    fn eval_binary(
        &self,
        op: &str,
        left: &Expr,
        right: &Expr,
        scope: &mut BTreeMap<String, Value>,
    ) -> EvalResult {
        // Short-circuit and/or.
        if op == "and" {
            let l = self.eval_expr(left, scope)?;
            if !l.truthy() {
                return Ok(l);
            }
            let r = self.eval_expr(right, scope)?;
            return Ok(Value::bool_val(r.truthy()).with_conf(min_conf(l.conf, r.conf)));
        }
        if op == "or" {
            let l = self.eval_expr(left, scope)?;
            if l.truthy() {
                return Ok(l);
            }
            return self.eval_expr(right, scope);
        }
        let l = self.eval_expr(left, scope)?;
        let r = self.eval_expr(right, scope)?;
        let out_kind = apply_binop(op, &l.kind, &r.kind)?;
        Ok(Value { kind: out_kind, conf: min_conf(l.conf, r.conf) })
    }

    fn eval_call(
        &self,
        callee: &Expr,
        args: &[Expr],
        scope: &mut BTreeMap<String, Value>,
    ) -> EvalResult {
        let name = match callee {
            Expr::Ident(n) => n.clone(),
            _ => return Err(EvalError::msg("cannot call non-identifier")),
        };
        let mut arg_vals = Vec::with_capacity(args.len());
        for a in args {
            arg_vals.push(self.eval_expr(a, scope)?);
        }
        if let Some(fn_decl) = self.program.fns.get(&name) {
            return self.invoke_fn(fn_decl, &arg_vals);
        }
        if let Some(it) = self.program.intents.get(&name) {
            return self.invoke_intent(it, &arg_vals);
        }
        if let Some(res) = call_builtin(&name, &arg_vals) {
            return res;
        }
        Err(EvalError::msg(format!("unknown callable {:?}", name)))
    }

    fn eval_attempt(
        &self,
        tries: &[Expr],
        scope: &mut BTreeMap<String, Value>,
    ) -> EvalResult {
        let mut last = Value::null();
        for t in tries {
            let v = self.eval_expr(t, scope)?;
            last = v.clone();
            if v.is_result_error() {
                continue;
            }
            return Ok(v);
        }
        Ok(last)
    }

    fn invoke_fn(&self, fn_decl: &FnDecl, args: &[Value]) -> EvalResult {
        let mut local: BTreeMap<String, Value> = BTreeMap::new();
        for (i, p) in fn_decl.params.iter().enumerate() {
            if i < args.len() {
                local.insert(p.name.clone(), args[i].clone());
            }
        }
        match self.exec_block(&fn_decl.body, &mut local) {
            Ok(_) => Ok(Value::null()),
            Err(EvalError::Return(v)) => Ok(v),
            Err(e) => Err(e),
        }
    }

    fn invoke_intent(&self, it: &IntentDecl, args: &[Value]) -> EvalResult {
        let adapter = self
            .adapter
            .as_ref()
            .ok_or_else(|| EvalError::msg(format!(
                "no adapter configured — cannot invoke intent {:?}",
                it.name
            )))?;
        let mut inputs: BTreeMap<String, Value> = BTreeMap::new();
        for (i, p) in it.params.iter().enumerate() {
            if i < args.len() {
                inputs.insert(p.name.clone(), args[i].clone());
            }
        }
        adapter.invoke(&it.goal, &it.constraints, &inputs)
    }
}

fn apply_binop(op: &str, l: &ValueKind, r: &ValueKind) -> Result<ValueKind, EvalError> {
    use ValueKind::*;
    if let (Number(lf), Number(rf)) = (l, r) {
        return Ok(match op {
            "+" => Number(lf + rf),
            "-" => Number(lf - rf),
            "*" => Number(lf * rf),
            "/" => Number(lf / rf),
            "%" => Number(lf % rf),
            "==" => Bool(lf == rf),
            "!=" => Bool(lf != rf),
            "<" => Bool(lf < rf),
            ">" => Bool(lf > rf),
            "<=" => Bool(lf <= rf),
            ">=" => Bool(lf >= rf),
            other => return Err(EvalError::msg(format!("binary {:?}: not supported on numbers", other))),
        });
    }
    if let (Text(ls), Text(rs)) = (l, r) {
        return Ok(match op {
            "+" => Text(format!("{ls}{rs}")),
            "==" => Bool(ls == rs),
            "!=" => Bool(ls != rs),
            other => return Err(EvalError::msg(format!("binary {:?}: not supported on texts", other))),
        });
    }
    if let (Bool(lb), Bool(rb)) = (l, r) {
        return Ok(match op {
            "==" => Bool(lb == rb),
            "!=" => Bool(lb != rb),
            other => return Err(EvalError::msg(format!("binary {:?}: not supported on bools", other))),
        });
    }
    // Heterogeneous equality must not panic — Python's == between
    // incompatible types is just False.
    if op == "==" {
        return Ok(ValueKind::Bool(false));
    }
    if op == "!=" {
        return Ok(ValueKind::Bool(true));
    }
    Err(EvalError::msg(format!(
        "binary {op:?}: incompatible operand types"
    )))
}

fn contains_value(coll: &ValueKind, elem: &ValueKind) -> bool {
    match coll {
        ValueKind::List(items) => items.iter().any(|v| value_eq(&v.kind, elem)),
        ValueKind::Text(s) => match elem {
            ValueKind::Text(needle) => s.contains(needle.as_str()),
            _ => false,
        },
        _ => false,
    }
}

fn value_eq(a: &ValueKind, b: &ValueKind) -> bool {
    use ValueKind::*;
    match (a, b) {
        (Number(x), Number(y)) => x == y,
        (Text(x), Text(y)) => x == y,
        (Bool(x), Bool(y)) => x == y,
        _ => false,
    }
}

// ------------ builtins ------------

fn min_conf_of(args: &[Value]) -> f64 {
    let mut m = 1.0f64;
    for a in args {
        if a.conf < m {
            m = a.conf;
        }
    }
    m
}

fn arg_text(v: &Value) -> Option<&str> {
    if let ValueKind::Text(s) = &v.kind { Some(s.as_str()) } else { None }
}

fn arg_number(v: &Value) -> Option<f64> {
    if let ValueKind::Number(n) = &v.kind { Some(*n) } else { None }
}

fn arg_list(v: &Value) -> Option<&Vec<Value>> {
    if let ValueKind::List(xs) = &v.kind { Some(xs) } else { None }
}

fn arg_record(v: &Value) -> Option<&BTreeMap<String, Value>> {
    if let ValueKind::Record(m) = &v.kind { Some(m) } else { None }
}

/// Returns `Some(Result)` if `name` is a recognized builtin (success or
/// runtime error), `None` if unknown — caller falls through.
fn call_builtin(name: &str, args: &[Value]) -> Option<EvalResult> {
    let minc = min_conf_of(args);
    match name {
        "length" => {
            let n = match args.first() {
                Some(v) => match &v.kind {
                    ValueKind::Text(s) => s.chars().count() as f64,
                    ValueKind::List(l) => l.len() as f64,
                    _ => 0.0,
                },
                None => 0.0,
            };
            Some(Ok(Value::number(n).with_conf(minc)))
        }
        "split" => {
            if args.len() < 2 {
                return Some(Err(EvalError::msg("split: need 2 args")));
            }
            let s = arg_text(&args[0]).unwrap_or("");
            let d = arg_text(&args[1]).unwrap_or("");
            let parts: Vec<Value> = if d.is_empty() {
                s.chars().map(|c| Value::text(c.to_string())).collect()
            } else {
                s.split(d).map(Value::text).collect()
            };
            Some(Ok(Value::list(parts).with_conf(minc)))
        }
        "join" => {
            if args.len() < 2 {
                return Some(Err(EvalError::msg("join: need 2 args")));
            }
            let list = match arg_list(&args[0]) { Some(l) => l, None => return Some(Ok(Value::text("").with_conf(minc))) };
            let delim = arg_text(&args[1]).unwrap_or("");
            let parts: Vec<String> = list.iter().map(|v| v.as_text()).collect();
            Some(Ok(Value::text(parts.join(delim)).with_conf(minc)))
        }
        "append" => {
            if args.len() < 2 {
                return Some(Err(EvalError::msg("append: need 2 args")));
            }
            let mut out = match arg_list(&args[0]) {
                Some(l) => l.clone(),
                None => Vec::new(),
            };
            out.push(args[1].clone());
            Some(Ok(Value::list(out).with_conf(minc)))
        }
        "range" => {
            if args.len() < 2 {
                return Some(Err(EvalError::msg("range: need 2 args")));
            }
            let start = arg_number(&args[0]).unwrap_or(0.0);
            let end = arg_number(&args[1]).unwrap_or(0.0);
            let mut out = Vec::new();
            let mut i = start;
            while i < end {
                out.push(Value::number(i));
                i += 1.0;
            }
            Some(Ok(Value::list(out).with_conf(minc)))
        }
        "to_text" => {
            let s = args.first().map(|v| v.as_text()).unwrap_or_default();
            Some(Ok(Value::text(s).with_conf(minc)))
        }
        "to_number" => {
            let s = args.first().map(|v| v.as_text()).unwrap_or_default();
            let trimmed = s.trim();
            match trimmed.parse::<f64>() {
                Ok(f) => Some(Ok(Value::number(f).with_conf(minc))),
                Err(_) => Some(Ok(make_error(format!("cannot convert to number: {s}")).with_conf(minc))),
            }
        }
        "trim" => {
            let s = args.first().map(|v| v.as_text()).unwrap_or_default();
            Some(Ok(Value::text(s.trim().to_string()).with_conf(minc)))
        }
        "upper" => {
            let s = args.first().map(|v| v.as_text()).unwrap_or_default();
            Some(Ok(Value::text(s.to_uppercase()).with_conf(minc)))
        }
        "lower" => {
            let s = args.first().map(|v| v.as_text()).unwrap_or_default();
            Some(Ok(Value::text(s.to_lowercase()).with_conf(minc)))
        }
        "get" => {
            if args.len() < 2 {
                return Some(Ok(Value::null().with_conf(minc)));
            }
            if let (Some(list), Some(idx)) = (arg_list(&args[0]), arg_number(&args[1])) {
                let i = idx as isize;
                if i >= 0 && (i as usize) < list.len() {
                    return Some(Ok(list[i as usize].clone()));
                }
                return Some(Ok(Value::null().with_conf(minc)));
            }
            if let (Some(map), Some(key)) = (arg_record(&args[0]), arg_text(&args[1])) {
                return Some(Ok(map.get(key).cloned().unwrap_or_else(Value::null)));
            }
            Some(Ok(Value::null().with_conf(minc)))
        }
        "is_ok" => {
            let v = if let Some(v) = args.first() { v } else { return Some(Ok(Value::bool_val(true))); };
            if let Some(m) = arg_record(v) {
                if matches!(m.get("_result"), Some(Value { kind: ValueKind::Bool(true), .. })) {
                    if let Some(Value { kind: ValueKind::Bool(b), .. }) = m.get("ok") {
                        return Some(Ok(Value::bool_val(*b).with_conf(minc)));
                    }
                }
            }
            Some(Ok(Value::bool_val(true).with_conf(minc)))
        }
        "is_error" => {
            let v = if let Some(v) = args.first() { v } else { return Some(Ok(Value::bool_val(false))); };
            if let Some(m) = arg_record(v) {
                if matches!(m.get("_result"), Some(Value { kind: ValueKind::Bool(true), .. })) {
                    if let Some(Value { kind: ValueKind::Bool(b), .. }) = m.get("ok") {
                        return Some(Ok(Value::bool_val(!b).with_conf(minc)));
                    }
                }
            }
            Some(Ok(Value::bool_val(false).with_conf(minc)))
        }
        "ok" => {
            let v = args.first().cloned().unwrap_or_else(Value::null);
            Some(Ok(make_ok(v)))
        }
        "error" => {
            let msg = args.first().map(|v| v.as_text()).unwrap_or_default();
            Some(Ok(make_error(msg)))
        }
        "unwrap" => {
            let v = if let Some(v) = args.first() { v.clone() } else { return Some(Ok(Value::null())); };
            if let ValueKind::Record(m) = &v.kind {
                if matches!(m.get("_result"), Some(Value { kind: ValueKind::Bool(true), .. })) {
                    if let Some(Value { kind: ValueKind::Bool(true), .. }) = m.get("ok") {
                        return Some(Ok(m.get("value").cloned().unwrap_or_else(Value::null)));
                    }
                    let err_text = m.get("error").map(|v| v.as_text()).unwrap_or_default();
                    return Some(Ok(Value::text(format!("UNWRAP_ERROR: {err_text}")).with_conf(0.0)));
                }
            }
            Some(Ok(v))
        }
        "unwrap_or" => {
            if args.len() < 2 {
                return Some(Ok(args.first().cloned().unwrap_or_else(Value::null)));
            }
            if let ValueKind::Record(m) = &args[0].kind {
                if matches!(m.get("_result"), Some(Value { kind: ValueKind::Bool(true), .. })) {
                    if let Some(Value { kind: ValueKind::Bool(true), .. }) = m.get("ok") {
                        return Some(Ok(m.get("value").cloned().unwrap_or_else(Value::null)));
                    }
                    return Some(Ok(args[1].clone()));
                }
            }
            Some(Ok(args[0].clone()))
        }
        "unwrap_error" => {
            let v = if let Some(v) = args.first() { v.clone() } else { return Some(Ok(Value::text("NOT_A_RESULT").with_conf(0.0))); };
            if let ValueKind::Record(m) = &v.kind {
                if matches!(m.get("_result"), Some(Value { kind: ValueKind::Bool(true), .. })) {
                    if let Some(Value { kind: ValueKind::Bool(true), .. }) = m.get("ok") {
                        return Some(Ok(Value::text("NOT_AN_ERROR").with_conf(0.0)));
                    }
                    return Some(Ok(m.get("error").cloned().unwrap_or_else(Value::null)));
                }
            }
            Some(Ok(Value::text("NOT_A_RESULT").with_conf(0.0)))
        }
        "abs" => {
            let n = args.first().and_then(arg_number).unwrap_or(0.0);
            Some(Ok(Value::number(n.abs()).with_conf(minc)))
        }
        "max" => {
            let list = match args.first().and_then(arg_list) {
                Some(l) if !l.is_empty() => l,
                _ => return Some(Ok(Value::null())),
            };
            let mut best = arg_number(&list[0]).unwrap_or(f64::NEG_INFINITY);
            for v in &list[1..] {
                if let Some(x) = arg_number(v) {
                    if x > best { best = x; }
                }
            }
            Some(Ok(Value::number(best).with_conf(minc)))
        }
        "min" => {
            let list = match args.first().and_then(arg_list) {
                Some(l) if !l.is_empty() => l,
                _ => return Some(Ok(Value::null())),
            };
            let mut best = arg_number(&list[0]).unwrap_or(f64::INFINITY);
            for v in &list[1..] {
                if let Some(x) = arg_number(v) {
                    if x < best { best = x; }
                }
            }
            Some(Ok(Value::number(best).with_conf(minc)))
        }
        "round" => {
            let x = args.first().and_then(arg_number).unwrap_or(0.0);
            let result = if let Some(nd) = args.get(1).and_then(arg_number) {
                let p = 10f64.powf(nd);
                round_ties_even(x * p) / p
            } else {
                round_ties_even(x)
            };
            Some(Ok(Value::number(result).with_conf(minc)))
        }
        "floor" => {
            let x = args.first().and_then(arg_number).unwrap_or(0.0);
            Some(Ok(Value::number(x.floor()).with_conf(minc)))
        }
        "ceil" => {
            let x = args.first().and_then(arg_number).unwrap_or(0.0);
            Some(Ok(Value::number(x.ceil()).with_conf(minc)))
        }
        "sqrt" => {
            let x = args.first().and_then(arg_number).unwrap_or(0.0);
            if x < 0.0 {
                return Some(Ok(make_error(format!("sqrt: negative argument {x}")).with_conf(minc)));
            }
            Some(Ok(Value::number(x.sqrt()).with_conf(minc)))
        }
        "pow" => {
            if args.len() < 2 { return Some(Ok(Value::null())); }
            let base = arg_number(&args[0]).unwrap_or(0.0);
            let exp = arg_number(&args[1]).unwrap_or(0.0);
            Some(Ok(Value::number(base.powf(exp)).with_conf(minc)))
        }
        _ => None,
    }
}

fn round_ties_even(x: f64) -> f64 {
    let diff = (x - x.trunc()).abs();
    if diff == 0.5 {
        let truncated = x.trunc();
        if (truncated as i64) % 2 == 0 {
            truncated
        } else if x > 0.0 {
            truncated + 1.0
        } else {
            truncated - 1.0
        }
    } else {
        x.round()
    }
}
