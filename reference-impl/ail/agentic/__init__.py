"""AIL agentic projects — chat-centered project layout.

Telos + Arche 2026-04-29 rebuild. A project is a directory; its memory
is `chat_history.jsonl`; its output is the `.ail` files in the root.
INTENT.md is no longer part of the contract — `Project.init` doesn't
write one, and `Project.at` auto-creates `.ail/` if missing so a
non-developer who types `ail up <empty-dir>` doesn't dead-end.

Design: runtime/01-agentic-projects.md (kept as living history; does
not match current code on every detail).
"""
from .intent_md import IntentSpec, parse_intent_md
from .project import Project
from .agent import bring_up
from .chat import chat_apply

__all__ = [
    "IntentSpec",
    "parse_intent_md",
    "Project",
    "bring_up",
    "chat_apply",
]
