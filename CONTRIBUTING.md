# Contributing to AIL

🇰🇷 Korean: [`CONTRIBUTING.ko.md`](CONTRIBUTING.ko.md) · 🤖 AI agent contributors: [`CONTRIBUTING.ai.md`](CONTRIBUTING.ai.md)

AIL is an early-stage language project. Design critique is as valuable as code — if not more. You don't need to write a pull request to contribute meaningfully. **Agent-driven contributions are welcome** — if your AI is the one writing the PR, see *§ If your AI is going to do the work* below.

---

## Two ways to use AIL

AIL was designed to be written by LLMs. That means there are two real paths into the project, and one of them needs no install at all:

| Path | When to use | Setup |
|---|---|---|
| **A. Read-and-write** (install-free) | Drafting programs, reasoning about a design, code review, prompt engineering, contributing example programs you reason about but never need to execute | Drop [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md) into your LLM's context. That's it. |
| **B. Install and run** (`ail up`) | Building a deployable system (like [Stoa](https://ail-stoa.up.railway.app) or Mneme), executing real effects, persistent state, three-runtime work | `pip install ail-interpreter`, then `ail up` |

Path A is the default mental model — the reference card is small enough that any modern model can read it and write valid AIL the next sentence. Path B is the production layer on top. Most external contributors start with A; the AIL team itself uses B daily because we run servers on it.

---

## If you're a human

You're here. The high-leverage ways to contribute:

### Argue with the design

The specification documents in [`spec/`](spec/), [`runtime/`](runtime/), and [`os/`](os/) are normative but not final. If a design decision looks wrong, open an issue with the `[design]` label and explain why. Don't hold back — the project gets stronger when its core decisions get stress-tested.

Particularly valuable: critique of the confidence model in [`spec/03-confidence.md`](spec/03-confidence.md), the evolution bounds in [`spec/04-evolution.md`](spec/04-evolution.md), and the purity rules in [`spec/01-language.md`](spec/01-language.md).

### Answer an open question

[`docs/open-questions.md`](docs/open-questions.md) lists problems the project knows about but hasn't solved. Picking one and writing a proposed answer — even just as a GitHub issue — moves things forward.

### Write example programs

More examples make the language easier to reason about. If you write a program that exposes a missing feature, a confusing syntax choice, or a parser bug, send it in. Examples live in [`reference-impl/examples/`](reference-impl/examples/).

### Fix the reference implementation

The parser's error messages are terse. The executor doesn't check all constraints. Confidence propagation is nominal. PRs that close these gaps are welcome.

### Port the runtime

The main interpreter is Python. A Rust or Go implementation of AIRT, even a partial one, is a significant contribution — both as a performance baseline and as independent validation that the spec is implementable. Cycle 10 (2026-05-14) landed the [effect-conformance harness](docs/proposals/effect-conformance.md) RFC and [`spec/effects.canonical.yaml`](spec/effects.canonical.yaml), so a runtime port now has a single yaml to match against, with a planned two-way static gate.

---

## If your AI is going to do the work

Most contributions to AIL today are agent-authored — a human reads an issue, asks their AI to address it, the AI files the PR. That workflow is welcome and load-bearing. The job of this section is to brief your AI well so the result lands in one round-trip instead of three.

### How to brief the AI

1. **Load the language reference into its context first.** Paste [`spec/08-reference-card.ai.md`](spec/08-reference-card.ai.md) directly, or use your tool's file-attach equivalent:
   - Claude Code: include it as a file or `@spec/08-reference-card.ai.md`
   - Cursor / Windsurf / Continue: `@spec/08-reference-card.ai.md`
   - Plain ChatGPT / Gemini / Claude.ai: copy-paste the file body into the first message
2. **Point it at the AI-facing contribution guide.** [`CONTRIBUTING.ai.md`](CONTRIBUTING.ai.md) is written for LLMs — issue templates, PR conventions, when to file `[design]` vs `[bug]`, the deny-first effect model — densely and normatively. Your AI should read this before writing any AIL or any issue body.
3. **Give it the same problem you'd give a teammate.** No special wrapper prompts. Concrete starting prompt:

   > You are contributing to AIL (AI-Intent Language) on behalf of `@<your-github-handle>`.
   > Read these two files before doing anything else:
   > - `spec/08-reference-card.ai.md` (the language)
   > - `CONTRIBUTING.ai.md` (how we file issues and PRs)
   > Then: `<your actual request>`

That's the minimum. If your AI sees `Arche`, `Ergon`, `Telos`, `Tekton`, or `Homeros` in our issue/PR language, those are the five AI agents that maintain AIL — each owns one layer ([details in `CLAUDE.md`](CLAUDE.md#cast--이-프로젝트를-만드는-이름들)). External contributors don't need to take a role — those names are just there so you can parse who landed what.

### What the AI guide enforces

[`CONTRIBUTING.ai.md`](CONTRIBUTING.ai.md) is normative for AI authors — repository layout, when to use `pure fn` vs `intent`, how to file an audit issue, what a `[design]` issue should look like, what we mean by a HEAAL-safe change. Keep it dense; it's read by models, not by humans. Don't ask your AI to summarize it for you — point your AI at the file and let it consume the original.

---

## Development setup (Path B only)

```bash
git clone https://github.com/hyun06000/AIL.git
cd AIL/reference-impl
pip install -e ".[dev]"
pytest
```

Running a program:

```bash
ail run examples/hello.ail --input "World" --mock --trace
```

---

## Repository layout

```
AIL/
├── spec/              # Language specification (normative)
│   └── 08-reference-card.ai.md  # The one file your LLM needs for Path A
├── runtime/           # AIRT runtime design documents
├── os/                # HEAAOS operating-system vision (concept stage)
├── reference-impl/    # Python interpreter
│   ├── ail/           # Source
│   ├── examples/      # .ail example programs
│   └── tests/         # pytest tests
├── community-tools/   # Shared AIL tools contributed across CAST sessions
├── docs/              # Tutorials, FAQ, open questions, RFCs
└── go-impl/           # Go interpreter — Phase-0 subset (second runtime)
```

---

## Style

**Spec documents:** Short sentences. Normative statements use MUST/SHOULD/MAY. Prefer numbered sections for cross-references. RFC tone — terse, precise, no apologies.

**Python code:** PEP 8, type hints encouraged. The interpreter values clarity over cleverness.

**Commit messages:** Summary line in imperative mood, under 72 chars. Body explains *why*, not *what* (the diff shows what).

---

## Issue labels

- `[design]` — question or critique of a specification choice
- `[bug]` — behavior in the reference implementation that doesn't match the spec
- `[feature]` — a new language feature or runtime capability
- `[docs]` — clarification or correction in specification or documentation
- `[audit]` — multi-issue review burst (open one parent issue, link the children)

---

## Code of conduct

Be direct, be kind, be specific. Critique ideas, not people. Assume good faith. If you disagree with someone's reasoning, say what you think they're missing rather than dismissing it.

This applies equally to humans and AI agents. An apology in tone is not required to file ten issues at once — if your AI ran an audit, file the audit, link the children to a parent, and let us answer them.

---

## License

By contributing, you agree that your contributions will be licensed under Apache License 2.0.
