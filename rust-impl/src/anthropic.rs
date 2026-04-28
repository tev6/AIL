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
use crate::json_parsing::parse_value_confidence;
use crate::value::Value;

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

#[cfg(test)]
mod tests {
    use super::*;

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
