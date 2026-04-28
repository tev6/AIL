//! Shared `(value, confidence)` extraction for model adapters.
//!
//! Mirrors `reference-impl/ail/runtime/json_parsing.py`. Language models
//! emit the JSON envelope an AIL `intent` expects with varying discipline:
//! they may wrap it in markdown code fences, prefix prose, or bury it in
//! explanation. This module is the tolerant parser shared by every
//! adapter so all of them handle the same malformed shapes the same way.

use std::collections::BTreeMap;

use serde_json::Value as JsonValue;

use crate::value::{Value, ValueKind};

/// Extract `(value, confidence)` from a model response.
///
/// Accepted shapes (in order of preference):
///   1. Pure JSON object `{"value":..., "confidence":...}`
///   2. Code-fenced JSON  ` ```json\n{...}\n``` `
///   3. JSON embedded in prose (first balanced `{...}` containing `"value"`)
///   4. Plain text — falls back to `(text, 0.5)`
///
/// Confidence is clamped to `[0.0, 1.0]`; missing or non-numeric becomes `0.5`.
pub fn parse_value_confidence(text: &str) -> (Value, f64) {
    let stripped = strip_code_fence(text.trim());

    if let Ok(json) = serde_json::from_str::<JsonValue>(stripped) {
        if let Some(obj) = json.as_object() {
            if obj.contains_key("value") {
                let value = json_to_value(obj.get("value").unwrap());
                let confidence = obj
                    .get("confidence")
                    .map(clamp_confidence)
                    .unwrap_or(0.5);
                return (value, confidence);
            }
        }
    }

    if let Some(slice) = extract_balanced_json(stripped) {
        if let Ok(json) = serde_json::from_str::<JsonValue>(slice) {
            if let Some(obj) = json.as_object() {
                if obj.contains_key("value") {
                    let value = json_to_value(obj.get("value").unwrap());
                    let confidence = obj
                        .get("confidence")
                        .map(clamp_confidence)
                        .unwrap_or(0.5);
                    return (value, confidence);
                }
            }
        }
    }

    (Value::text(text.to_string()), 0.5)
}

/// Walk a JSON value and produce the matching AIL `Value`.
pub fn json_to_value(j: &JsonValue) -> Value {
    match j {
        JsonValue::Null => Value::null(),
        JsonValue::Bool(b) => Value::bool_val(*b),
        JsonValue::Number(n) => {
            if let Some(f) = n.as_f64() {
                Value::number(f)
            } else {
                Value::text(n.to_string())
            }
        }
        JsonValue::String(s) => Value::text(s.clone()),
        JsonValue::Array(arr) => Value::list(arr.iter().map(json_to_value).collect()),
        JsonValue::Object(map) => {
            let mut bm = BTreeMap::new();
            for (k, v) in map {
                bm.insert(k.clone(), json_to_value(v));
            }
            Value { kind: ValueKind::Record(bm), conf: 1.0 }
        }
    }
}

fn clamp_confidence(j: &JsonValue) -> f64 {
    let raw = j.as_f64().unwrap_or(0.5);
    raw.clamp(0.0, 1.0)
}

fn strip_code_fence(text: &str) -> &str {
    let t = text.trim();
    if !t.starts_with("```") {
        return t;
    }
    let after_first = match t.find('\n') {
        Some(i) => &t[i + 1..],
        None => return t,
    };
    let body = if let Some(stripped) = after_first.strip_suffix("```") {
        stripped
    } else {
        after_first
    };
    body.trim()
}

fn extract_balanced_json(text: &str) -> Option<&str> {
    // First balanced `{...}` substring that contains `"value"`, or None.
    let bytes = text.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] == b'{' {
            let mut depth: i32 = 0;
            let mut in_str = false;
            let mut escape = false;
            let mut j = i;
            while j < bytes.len() {
                let c = bytes[j];
                if in_str {
                    if escape {
                        escape = false;
                    } else if c == b'\\' {
                        escape = true;
                    } else if c == b'"' {
                        in_str = false;
                    }
                } else {
                    match c {
                        b'"' => in_str = true,
                        b'{' => depth += 1,
                        b'}' => {
                            depth -= 1;
                            if depth == 0 {
                                let slice = &text[i..=j];
                                if slice.contains("\"value\"") {
                                    return Some(slice);
                                }
                                break;
                            }
                        }
                        _ => {}
                    }
                }
                j += 1;
            }
        }
        i += 1;
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn pure_json_value_and_confidence() {
        let (v, c) = parse_value_confidence(r#"{"value": "hello", "confidence": 0.9}"#);
        assert!(matches!(v.kind, ValueKind::Text(ref s) if s == "hello"));
        assert!((c - 0.9).abs() < 1e-9);
    }

    #[test]
    fn code_fenced_json() {
        let raw = "```json\n{\"value\": 42, \"confidence\": 1.0}\n```";
        let (v, c) = parse_value_confidence(raw);
        assert!(matches!(v.kind, ValueKind::Number(n) if n == 42.0));
        assert_eq!(c, 1.0);
    }

    #[test]
    fn embedded_in_prose() {
        let raw = r#"Here you go: {"value": [1, 2, 3], "confidence": 0.7}, hope that helps."#;
        let (v, c) = parse_value_confidence(raw);
        match v.kind {
            ValueKind::List(l) => assert_eq!(l.len(), 3),
            other => panic!("expected list, got {other:?}"),
        }
        assert!((c - 0.7).abs() < 1e-9);
    }

    #[test]
    fn confidence_clamped_high() {
        let (_, c) = parse_value_confidence(r#"{"value": "x", "confidence": 1.5}"#);
        assert_eq!(c, 1.0);
    }

    #[test]
    fn confidence_missing_defaults_05() {
        let (_, c) = parse_value_confidence(r#"{"value": "x"}"#);
        assert_eq!(c, 0.5);
    }

    #[test]
    fn plain_text_fallback() {
        let (v, c) = parse_value_confidence("just a sentence with no JSON");
        assert!(matches!(v.kind, ValueKind::Text(_)));
        assert_eq!(c, 0.5);
    }
}
