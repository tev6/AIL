//! Runtime value representation. Mirrors `go-impl/eval.go:Value`.
//!
//! Every AIL value carries a confidence in [0.0, 1.0]. Provenance is
//! elided in the v0 Rust runtime — the Python reference owns that
//! field; the spec defines provenance independently of any runtime.

use std::collections::BTreeMap;
use std::fmt;

#[derive(Debug, Clone, PartialEq)]
pub enum ValueKind {
    Number(f64),
    Text(String),
    Bool(bool),
    List(Vec<Value>),
    /// JSON-shaped record (string-keyed map). Used for Result envelopes
    /// `{_result, ok, value|error}` and any user-built `make_record`.
    Record(BTreeMap<String, Value>),
    Null,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Value {
    pub kind: ValueKind,
    pub conf: f64,
}

impl Value {
    pub fn number(v: f64) -> Self {
        Self { kind: ValueKind::Number(v), conf: 1.0 }
    }
    pub fn text<S: Into<String>>(v: S) -> Self {
        Self { kind: ValueKind::Text(v.into()), conf: 1.0 }
    }
    pub fn bool_val(v: bool) -> Self {
        Self { kind: ValueKind::Bool(v), conf: 1.0 }
    }
    pub fn list(v: Vec<Value>) -> Self {
        Self { kind: ValueKind::List(v), conf: 1.0 }
    }
    pub fn record(m: BTreeMap<String, Value>) -> Self {
        Self { kind: ValueKind::Record(m), conf: 1.0 }
    }
    pub fn null() -> Self {
        Self { kind: ValueKind::Null, conf: 1.0 }
    }
    pub fn with_conf(mut self, c: f64) -> Self {
        self.conf = c;
        self
    }

    pub fn truthy(&self) -> bool {
        match &self.kind {
            ValueKind::Bool(b) => *b,
            ValueKind::Number(n) => *n != 0.0,
            ValueKind::Text(s) => !s.is_empty(),
            ValueKind::List(l) => !l.is_empty(),
            ValueKind::Null => false,
            ValueKind::Record(_) => true,
        }
    }

    /// Result-shaped error: `{_result: true, ok: false, error: ...}`.
    pub fn is_result_error(&self) -> bool {
        if let ValueKind::Record(m) = &self.kind {
            matches!(m.get("_result"), Some(Value { kind: ValueKind::Bool(true), .. }))
                && matches!(m.get("ok"), Some(Value { kind: ValueKind::Bool(false), .. }))
        } else {
            false
        }
    }

    pub fn as_text(&self) -> String {
        match &self.kind {
            ValueKind::Text(s) => s.clone(),
            ValueKind::Number(n) => format_number(*n),
            ValueKind::Bool(b) => if *b { "true".into() } else { "false".into() },
            ValueKind::Null => String::new(),
            ValueKind::List(items) => {
                let parts: Vec<String> = items.iter().map(|v| v.as_text()).collect();
                format!("[{}]", parts.join(", "))
            }
            ValueKind::Record(m) => {
                let mut parts: Vec<String> = Vec::with_capacity(m.len());
                for (k, v) in m {
                    parts.push(format!("{k}: {}", v.as_text()));
                }
                format!("{{{}}}", parts.join(", "))
            }
        }
    }
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.as_text())
    }
}

fn format_number(n: f64) -> String {
    if n.is_finite() && n.trunc() == n {
        format!("{}", n as i64)
    } else {
        format!("{n}")
    }
}

pub(crate) fn min_conf(a: f64, b: f64) -> f64 {
    if a < b { a } else { b }
}

/// Result envelope helpers — shape matches Python `executor.py`.
pub fn make_ok(value: Value) -> Value {
    let conf = value.conf;
    let mut m = BTreeMap::new();
    m.insert("_result".into(), Value::bool_val(true));
    m.insert("ok".into(), Value::bool_val(true));
    m.insert("value".into(), value);
    Value::record(m).with_conf(conf)
}

pub fn make_error<S: Into<String>>(msg: S) -> Value {
    let mut m = BTreeMap::new();
    m.insert("_result".into(), Value::bool_val(true));
    m.insert("ok".into(), Value::bool_val(false));
    m.insert("error".into(), Value::text(msg));
    Value::record(m)
}
