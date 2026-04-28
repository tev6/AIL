//! Ollama adapter — port of `reference-impl/ail/runtime/ollama_adapter.py`.
//!
//! Ships the same intent contract as the Anthropic adapter (system prompt
//! that demands `{"value":..., "confidence":...}` output, tolerant
//! parsing) but talks to a local Ollama server. No auth, no API cost,
//! works offline.
//!
//! Environment:
//!   OLLAMA_MODEL   — model tag (default: `ail-coder:7b-v3` to match the
//!                    canonical fine-tuned model the project ships).
//!                    Override per-run with `--adapter ollama` and an
//!                    `OLLAMA_MODEL=qwen2.5-coder:14b-instruct-q4_K_M`
//!                    style env var.
//!   OLLAMA_HOST    — base URL (default: `http://localhost:11434`).
//!
//! Wire transport is `curl` (same rationale as Anthropic — no native HTTP
//! crate). Uses POST `/api/chat` with `stream:false`.

use std::collections::BTreeMap;
use std::io::Write;
use std::process::{Command, Stdio};

use serde_json::{json, Value as JsonValue};

use crate::eval::{Adapter, EvalError, EvalResult};
use crate::json_parsing::parse_value_confidence;
use crate::value::Value;

pub const DEFAULT_MODEL: &str = "ail-coder:7b-v3";
pub const DEFAULT_HOST: &str = "http://localhost:11434";

pub struct OllamaAdapter {
    model: String,
    host: String,
}

impl OllamaAdapter {
    /// Reads `OLLAMA_MODEL` and `OLLAMA_HOST` from env; falls back to
    /// canonical defaults so a user with Ollama already running locally
    /// gets a sensible setup with zero config.
    pub fn from_env() -> Result<Self, EvalError> {
        let model = std::env::var("OLLAMA_MODEL").unwrap_or_else(|_| DEFAULT_MODEL.to_string());
        let host = std::env::var("OLLAMA_HOST").unwrap_or_else(|_| DEFAULT_HOST.to_string());
        Ok(Self::new(model, host))
    }

    pub fn new(model: String, host: String) -> Self {
        // Strip trailing slash so `host` + path always concatenates cleanly.
        let host = host.trim_end_matches('/').to_string();
        Self { model, host }
    }

    fn build_system_prompt(&self, goal: &str, constraints: &[String]) -> String {
        let mut lines: Vec<String> = vec![
            "You are executing an AIL intent. AIL programs describe *intent*;".into(),
            "you produce the result that satisfies the declared goal and constraints.".into(),
            String::new(),
            "Respond in this exact JSON format (no surrounding prose, no code fence):".into(),
            "  {\"value\": <your result>, \"confidence\": <number 0.0 to 1.0>}".into(),
            String::new(),
            "Confidence reflects your calibrated belief that your result satisfies".into(),
            "the goal. Be honest; 1.0 means certain, 0.5 unsure, 0.0 unable.".into(),
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

impl Adapter for OllamaAdapter {
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
            "stream": false,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        });
        let body_bytes = serde_json::to_vec(&body)
            .map_err(|e| EvalError::msg(format!("ollama: serialize body: {e}")))?;

        let url = format!("{}/api/chat", self.host);
        let mut child = Command::new("curl")
            .args([
                "-sS",
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json",
                "--data-binary",
                "@-",
                &url,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| EvalError::msg(format!("ollama: spawn curl: {e}")))?;
        {
            let stdin = child
                .stdin
                .as_mut()
                .ok_or_else(|| EvalError::msg("ollama: stdin unavailable"))?;
            stdin
                .write_all(&body_bytes)
                .map_err(|e| EvalError::msg(format!("ollama: write body: {e}")))?;
        }
        let output = child
            .wait_with_output()
            .map_err(|e| EvalError::msg(format!("ollama: wait curl: {e}")))?;
        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(EvalError::msg(format!(
                "ollama: curl failed (exit {}): {stderr}\n  is `ollama serve` running on {}?",
                output.status.code().unwrap_or(-1),
                self.host
            )));
        }

        let resp: JsonValue = serde_json::from_slice(&output.stdout).map_err(|e| {
            let body = String::from_utf8_lossy(&output.stdout);
            EvalError::msg(format!("ollama: parse response: {e}\n  raw: {body}"))
        })?;

        // Ollama errors: `{"error":"..."}`.
        if let Some(err) = resp.get("error").and_then(|e| e.as_str()) {
            return Err(EvalError::msg(format!("ollama: API error: {err}")));
        }

        // Success shape: `{"message": {"role":"assistant", "content":"..."}, ...}`.
        let text = resp
            .get("message")
            .and_then(|m| m.get("content"))
            .and_then(|c| c.as_str())
            .ok_or_else(|| EvalError::msg("ollama: response missing message.content"))?
            .to_string();

        if text.is_empty() {
            return Err(EvalError::msg("ollama: empty assistant response"));
        }

        let (value, confidence) = parse_value_confidence(&text);
        Ok(value.with_conf(confidence))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn defaults_when_env_unset() {
        // We can't easily mutate env in a unit test without flakes; just
        // build with explicit args and confirm the trim-slash invariant.
        let a = OllamaAdapter::new("foo".into(), "http://localhost:11434/".into());
        assert!(!a.host.ends_with('/'));
        assert_eq!(a.model, "foo");
    }
}
