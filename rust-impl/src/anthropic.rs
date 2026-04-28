//! Anthropic adapter — port of `reference-impl/ail/runtime/anthropic_adapter.py`.
//!
//! Translates an AIL `intent` invocation into a Messages API call and parses
//! the result into a `Value` with calibrated confidence. Wire transport is
//! `curl` (shelled out via `std::process::Command`) so the binary stays
//! HTTP-stack free — only `serde_json` is added.
//!
//! Token detection mirrors the Python reference: subscription OAuth tokens
//! issued by `claude setup-token` start with `sk-ant-oat` and are sent as
//! `Authorization: Bearer …`; standard API keys (`sk-ant-api…`) keep using
//! `X-Api-Key`. Detection is by prefix so users don't have to set a
//! separate env var. (Arche urgent letter 2026-04-28.)

use std::collections::BTreeMap;
use std::io::Write;
use std::process::{Command, Stdio};

use serde_json::{json, Value as JsonValue};

use crate::eval::{Adapter, EvalError, EvalResult};
use crate::value::{Value, ValueKind};

const API_URL: &str = "https://api.anthropic.com/v1/messages";
const API_VERSION: &str = "2023-06-01";
pub const DEFAULT_MODEL: &str = "claude-sonnet-4-5";

pub struct AnthropicAdapter {
    model: String,
    token: String,
    is_oauth: bool,
}

impl AnthropicAdapter {
    /// Reads the token from `ANTHROPIC_API_KEY`; errors if unset.
    pub fn from_env() -> Result<Self, EvalError> {
        let token = std::env::var("ANTHROPIC_API_KEY").map_err(|_| {
            EvalError::msg(
                "ANTHROPIC_API_KEY not set. Export it (or for Pro/Max plans run `claude setup-token`).",
            )
        })?;
        Ok(Self::with_token(token, DEFAULT_MODEL.to_string()))
    }

    pub fn with_token(token: String, model: String) -> Self {
        let is_oauth = token.starts_with("sk-ant-oat");
        Self { model, token, is_oauth }
    }

    fn auth_header(&self) -> String {
        if self.is_oauth {
            format!("Authorization: Bearer {}", self.token)
        } else {
            format!("X-Api-Key: {}", self.token)
        }
    }

    fn build_system_prompt(&self, goal: &str, constraints: &[String]) -> String {
        let mut lines: Vec<String> = vec![
            "You are executing an AIL intent. AIL programs describe *intent*;".into(),
            "you produce the result that satisfies the declared goal and constraints.".into(),
            String::new(),
            "Respond in this exact JSON format (no surrounding prose, no code fence):".into(),
            "  {\"value\": <your result>, \"confidence\": <number 0.0 to 1.0>}".into(),
            String::new(),
            "The confidence reflects your calibrated belief that your result".into(),
            "satisfies the goal under the given context. Be honest; 1.0 means".into(),
            "you are certain, 0.5 means unsure, 0.0 means you could not produce".into(),
            "a satisfactory result.".into(),
            String::new(),
            format!("GOAL: {goal}"),
        ];
        if !constraints.is_empty() {
            lines.push(String::new());
            lines.push("CONSTRAINTS:".into());
            for c in constraints {
                lines.push(format!("  - {c}"));
            }
        }
        lines.join("\n")
    }

    fn build_user_prompt(&self, inputs: &BTreeMap<String, Value>) -> String {
        if inputs.is_empty() {
            return "(no input)".into();
        }
        if inputs.len() == 1 {
            let (k, v) = inputs.iter().next().unwrap();
            return format!("{k}: {}", v.as_text());
        }
        inputs
            .iter()
            .map(|(k, v)| format!("{k}: {}", v.as_text()))
            .collect::<Vec<_>>()
            .join("\n")
    }
}

impl Adapter for AnthropicAdapter {
    fn invoke(
        &self,
        goal: &str,
        constraints: &[String],
        inputs: &BTreeMap<String, Value>,
    ) -> EvalResult {
        let system = self.build_system_prompt(goal, constraints);
        let user = self.build_user_prompt(inputs);

        let body = json!({
            "model": self.model,
            "max_tokens": 8192,
            "system": system,
            "messages": [
                {"role": "user", "content": user},
            ],
        });

        let body_bytes = serde_json::to_vec(&body)
            .map_err(|e| EvalError::msg(format!("anthropic: serialize body: {e}")))?;

        // POST via curl. Body goes over stdin (`@-`) so the API token is
        // the only thing in the argv — payload size and content stay off
        // the process table.
        let mut child = Command::new("curl")
            .args([
                "-sS",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "-H",
                &format!("anthropic-version: {API_VERSION}"),
                "-H",
                &self.auth_header(),
                "--data-binary",
                "@-",
                API_URL,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| EvalError::msg(format!("anthropic: spawn curl: {e} — is curl installed?")))?;
        {
            let stdin = child
                .stdin
                .as_mut()
                .ok_or_else(|| EvalError::msg("anthropic: stdin unavailable"))?;
            stdin
                .write_all(&body_bytes)
                .map_err(|e| EvalError::msg(format!("anthropic: write body: {e}")))?;
        }
        let output = child
            .wait_with_output()
            .map_err(|e| EvalError::msg(format!("anthropic: wait curl: {e}")))?;
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(EvalError::msg(format!(
                "anthropic: curl failed (exit {}): {stderr}",
                output.status.code().unwrap_or(-1)
            )));
        }

        let resp: JsonValue = serde_json::from_slice(&output.stdout).map_err(|e| {
            let body = String::from_utf8_lossy(&output.stdout);
            EvalError::msg(format!("anthropic: parse response: {e}\n  raw: {body}"))
        })?;

        // API error envelope
        if let Some(err) = resp.get("error") {
            let msg = err.get("message").and_then(|m| m.as_str()).unwrap_or("(no message)");
            let kind = err.get("type").and_then(|m| m.as_str()).unwrap_or("error");
            return Err(EvalError::msg(format!("anthropic: API {kind}: {msg}")));
        }

        // Extract first content[*] text block.
        let content = resp
            .get("content")
            .and_then(|c| c.as_array())
            .ok_or_else(|| EvalError::msg("anthropic: response has no content array"))?;
        let mut text = String::new();
        for block in content {
            if block.get("type").and_then(|t| t.as_str()) == Some("text") {
                if let Some(t) = block.get("text").and_then(|t| t.as_str()) {
                    text.push_str(t);
                }
            }
        }
        if text.is_empty() {
            return Err(EvalError::msg("anthropic: response has no text content"));
        }

        let (value, confidence) = parse_value_confidence(&text);
        Ok(value.with_conf(confidence))
    }
}

/// Tolerant `(value, confidence)` extraction. Mirrors
/// `reference-impl/ail/runtime/json_parsing.py:parse_value_confidence`.
///
/// Accepted shapes (in order of preference):
///   1. Pure JSON object `{"value":..., "confidence":...}`
///   2. Code-fenced JSON  ` ```json\n{...}\n``` `
///   3. JSON embedded in prose (first balanced `{...}` containing `"value"`)
///   4. Plain text — falls back to (text, 0.5)
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

fn json_to_value(j: &JsonValue) -> Value {
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
            // Detect Result-shaped envelopes for parity with native ok()/error()
            // — pure JSON `{"_result":true,...}` round-trips correctly.
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
    // Scan for the first '{' that opens a balanced object containing `"value"`.
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

    #[test]
    fn auth_header_oauth() {
        let a = AnthropicAdapter::with_token("sk-ant-oat01-xyz".into(), DEFAULT_MODEL.into());
        assert!(a.auth_header().starts_with("Authorization: Bearer "));
    }

    #[test]
    fn auth_header_api_key() {
        let a = AnthropicAdapter::with_token("sk-ant-api03-xyz".into(), DEFAULT_MODEL.into());
        assert!(a.auth_header().starts_with("X-Api-Key: "));
    }
}
