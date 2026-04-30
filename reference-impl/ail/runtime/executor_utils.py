"""Pure utility functions extracted from executor.py (Stage 0 of executor split RFC).

No behavior change — these functions are mechanically lifted from
executor.py's tail. Each is module-level (no `self`) and was already
free of `Executor`-state coupling. Tests cover them via integration.
"""

from __future__ import annotations

from typing import Any

from ..parser.ast import (
    ContextDecl, Literal, Identifier, Expr, MatchArm,
)
from .provenance import Origin, LITERAL_ORIGIN


def _json_normalize(value):
    """Convert an AIL runtime value into something json.dumps can serialize.

    AIL has no dict literal syntax, so the canonical way to build an
    object inline is a list of two-element [key, value] lists — same
    convention `http.post` uses for `headers`. This helper recognises
    that shape recursively: a list whose every element is a 2-list with
    a string-ish first element becomes a JSON object; any other list
    becomes a JSON array. Python dicts pass through (from intents or
    earlier parse_json calls). Primitives pass through after Result-
    error detection (errors shouldn't silently encode to {"_result":
    true, ...} — they should propagate).

    Raises ValueError if given an ok-Result or error-Result by
    mistake; the caller should unwrap() first so the encoding is of
    the payload, not the wrapper.
    """
    if isinstance(value, dict) and value.get("_result") is True:
        if value.get("ok"):
            raise ValueError(
                "encode_json: got an ok-Result; call unwrap() first")
        raise ValueError(
            "encode_json: got an error-Result; cannot serialize an error")
    if isinstance(value, list):
        if value and all(
            isinstance(e, list) and len(e) == 2 and isinstance(e[0], str)
            for e in value
        ):
            return {e[0]: _json_normalize(e[1]) for e in value}
        return [_json_normalize(e) for e in value]
    if isinstance(value, dict):
        return {str(k): _json_normalize(v) for k, v in value.items()}
    return value


def _strip_html(source: str) -> str:
    """Extract visible text content from an HTML document.

    Uses stdlib html.parser. Drops everything inside <script> and
    <style> tags so a minified page doesn't flood the result with
    JS source. Decodes common named entities. Normalises run-together
    whitespace so what reaches the next stage is comparable to what a
    human would see in the browser.

    Not a sanitizer — output is for LLM consumption, not re-embedding.
    """
    from html.parser import HTMLParser
    import re as _re

    class _Collector(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.skip = 0

        def handle_starttag(self, tag, attrs):
            if tag.lower() in ("script", "style"):
                self.skip += 1

        def handle_endtag(self, tag):
            if tag.lower() in ("script", "style") and self.skip > 0:
                self.skip -= 1

        def handle_data(self, data):
            if self.skip == 0:
                self.parts.append(data)

    c = _Collector()
    try:
        c.feed(source)
        c.close()
    except Exception:
        pass
    joined = "".join(c.parts)
    joined = _re.sub(r"[ \t\f\v]+", " ", joined)
    joined = _re.sub(r"\n[ \t]+", "\n", joined)
    joined = _re.sub(r"\n{3,}", "\n\n", joined)
    return joined.strip()


def _default_context() -> ContextDecl:
    """Construct the minimum 'default' context when not declared."""
    return ContextDecl(
        name="default",
        extends=None,
        fields={
            "register": Literal(value="neutral"),
            "latency_budget": Literal(value=5000),
            "audience": Literal(value="general"),
        },
        overrides=set(),
    )


def _apply_binop(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        return left / right
    if op == "%":
        return left % right
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == "<":
        return left < right
    if op == ">":
        return left > right
    if op == "<=":
        return left <= right
    if op == ">=":
        return left >= right
    raise ValueError(f"unsupported binop: {op}")


def _truncate(v: Any, n: int = 200) -> Any:
    s = str(v)
    if len(s) <= n:
        return v
    return s[:n] + "…"


def _pattern_matches(pattern: Expr, subject) -> tuple[bool, str | None]:
    """Check whether a pattern matches the subject's value.

    Returns (matched, binding_name) where `binding_name` is non-None if
    the pattern introduces a variable binding (identifier other than `_`).

    v1 patterns:
      - Literal: exact equality with subject.value.
      - Identifier("_"): wildcard — always matches, no binding.
      - Identifier(other): variable binding — always matches, binds.

    Other expression types are rejected as invalid patterns.
    """
    if isinstance(pattern, Literal):
        return (pattern.value == subject.value, None)
    if isinstance(pattern, Identifier):
        if pattern.name == "_":
            return (True, None)
        if pattern.name == "true":
            return (subject.value is True, None)
        if pattern.name == "false":
            return (subject.value is False, None)
        return (True, pattern.name)
    raise RuntimeError(
        f"match pattern must be a literal, '_', or identifier; "
        f"got {type(pattern).__name__}"
    )


def _confidence_guard_passes(arm: MatchArm, subject_conf: float) -> bool:
    """Check the optional `with confidence OP N` guard on a match arm."""
    if arm.confidence_op is None or arm.confidence_threshold is None:
        return True
    op = arm.confidence_op
    t = arm.confidence_threshold
    if op == ">":
        return subject_conf > t
    if op == "<":
        return subject_conf < t
    if op == ">=":
        return subject_conf >= t
    if op == "<=":
        return subject_conf <= t
    if op == "==":
        return subject_conf == t
    return False


def _is_result_error(value: Any) -> bool:
    """True if `value` is a Result wrapping an error (i.e. error(...))."""
    return (isinstance(value, dict)
            and value.get("_result") is True
            and value.get("ok") is False)


def _dominant_origin(*values) -> Origin:
    """Return the first non-literal origin among the given ConfidentValues.

    If every argument is a literal, returns LITERAL_ORIGIN. Used by
    binary/unary/field operations that don't themselves create a new origin
    node but inherit from their operand's history.
    """
    for v in values:
        o = v.origin if hasattr(v, "origin") else LITERAL_ORIGIN
        if o is not LITERAL_ORIGIN:
            return o
    return LITERAL_ORIGIN


def _default_ask_human(question: str, *, expect: str = "text") -> Any:
    """Default human prompt via stdin."""
    print(f"\n[ASK HUMAN] {question}")
    answer = input(f"  ({expect}) > ").strip()
    if expect == "yes/no":
        return answer.lower() in ("y", "yes", "true", "1")
    return answer
