# AI Interactions Log

> **Stretch features only.** Only fill in the sections that apply to stretch features you attempted. If you did not attempt a stretch feature, leave its section blank or delete it. This file is not required for the core project.

---

## Agentic Workflow (SF8)

> Document your experience using an AI agent (e.g., Cursor Agent, Claude, Copilot) to make multi-step changes autonomously.

**What task did you give the agent?**

I used Claude Code (an AI coding agent) to add an advanced AI feature to my
finished recommender. The goal: add a Retrieval-Augmented Generation (RAG)
feature and a Streamlit UI, without breaking the existing deterministic scorer.
I asked it to read my whole codebase and old README first, then brainstorm and
plan before writing any code.

**Prompts used:**

- "Go through the entire codebase and understand exactly what this app does...
  I was thinking we could implement a RAG feature as our improvement, and then
  add a Streamlit UI. Let's brainstorm and plan before writing any code."
- After it proposed a plan and asked clarifying questions, I chose: reuse my
  existing scorer as the retriever, default to `claude-sonnet-5`, and unify the
  duplicated OOP/functional code paths.
- "Yes, let's proceed with this."

**What did the agent generate or change?**

- Unified `src/recommender.py` so `score_song` is the single scoring
  implementation and the `Recommender` class delegates to it (its methods were
  previously unimplemented stubs). Added `UserProfile.target_valence` and a
  `to_prefs()` adapter.
- Added `src/rag.py` — the parse → retrieve → generate pipeline, with a
  no-key/error fallback to the deterministic recommender, an anti-hallucination
  guardrail, and per-stage logging.
- Added `src/app.py` — a Streamlit UI with a RAG tab, a manual-profile tab, a
  transparency panel, and a deterministic-vs-RAG comparison view.
- Added `tests/test_rag.py` (mocked Anthropic client) and expanded
  `tests/test_recommender.py` with scoring-correctness and OOP/functional
  parity tests. Updated `requirements.txt` and the docs.

**What did you verify or fix manually?**

- Confirmed `pytest` passes (15 tests) and that `python -m src.main` still
  produces my documented CLI output.
- Confirmed the app runs with **no** API key via the deterministic fallback.
- The agent flagged something I hadn't noticed: my `Recommender` class methods
  were placeholder stubs and the starter tests were passing by accident. I had
  it fix that as part of the work.
- The live LLM path needs my own `ANTHROPIC_API_KEY`, which wasn't available in
  the agent's environment — so I verify that path myself by running the
  Streamlit app locally with my key set.

---

## Design Pattern (SF10)

> Document how AI helped you choose or implement a design pattern.

**Which design pattern did you use?**

<!-- e.g., Strategy, Factory, Observer, etc. -->

**How did AI help you brainstorm or implement it?**

<!-- Describe the conversation or suggestions that led to your decision -->

**How does the pattern appear in your final code?**

<!-- Point to the relevant class or method -->
