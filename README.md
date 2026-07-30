# 🎧 Music Recommender Simulation — with RAG + Streamlit

A content-based music recommender that scores songs against a listener's taste
profile, now upgraded with a **Retrieval-Augmented Generation (RAG)** feature
and a **Streamlit** UI.

> These sections document the improvements (RAG + UI + setup). Merge them into
> your main project README as needed.

---

## What's new

### 1. RAG feature (the advanced AI feature)

The original recommender only matched a profile with **exact-string** genre/mood
comparisons, so phrasing like `"high-energy pop"` never matched the catalog's
`"pop"`, and `"sad"` never matched `"melancholic"` (documented in the model
card). RAG fixes exactly that, in three stages:

1. **Understand** — Gemini (`gemini-3.6-flash`) parses a free-text request into a
   structured `UserProfile`, using **catalog-derived enums** so the parsed
   genre/mood are guaranteed to be vocabulary that exists in `songs.csv`.
2. **Retrieve** — that profile is fed to the **existing deterministic scorer**
   (`score_song` / `recommend_songs`) to pull the top-*k* candidate songs. The
   catalog is the knowledge base; the scorer is the retriever.
3. **Generate** — Gemini writes a grounded, plain-language recommendation using
   **only** the retrieved songs' real attributes.

The retrieved songs are what Gemini reasons over — the AI actively uses the
retrieved data to form its answer, rather than printing it alongside a canned
response.

**Guardrails, logging, and reliability:**
- If `GEMINI_API_KEY` is missing or an API call fails, the app **degrades
  gracefully** to the pure deterministic recommender (a keyword heuristic builds
  the profile). The app and the tests run with no key and no network.
- **Anti-hallucination check:** any catalog song Gemini names that wasn't
  retrieved is flagged as a warning.
- Every stage is logged (query → parsed profile → retrieved songs → model → token
  usage), surfaced in the UI's transparency panel.

### 2. Streamlit UI

- **Describe your vibe (RAG):** free-text box → parsed profile → retrieved songs
  → grounded recommendation.
- **Manual profile:** sliders/dropdowns that drive the deterministic scorer
  directly (no LLM).
- **Deterministic-vs-RAG comparison** toggle that shows the raw exact-string
  ranking next to the RAG result — making the model card's biases visible.

### 3. Cleanup

The `Recommender` class and `score_song`/`recommend_songs` functions were two
parallel, inconsistent code paths (the class methods were unimplemented stubs
that passed the starter tests by accident). They're now unified: `score_song`
is the single scoring implementation, and `Recommender` delegates to it, so the
OOP and functional APIs can never drift apart. `UserProfile` gained a
`target_valence` field and a `to_prefs()` adapter.

---

## Architecture

```
data/songs.csv                 # 30-song catalog (the knowledge base)
src/recommender.py             # deterministic core: Song, UserProfile, score_song, Recommender
src/rag.py                     # RAG layer: parse -> retrieve -> generate, guardrails, fallback
src/app.py                     # Streamlit UI
src/main.py                    # CLI runner
tests/test_recommender.py      # scoring + OOP/functional parity
tests/test_rag.py              # RAG pipeline with a mocked Gemini client
```

---

## Setup

1. (Optional) Create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate      # Mac / Linux
   .venv\Scripts\activate         # Windows
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set your Gemini API key (required only for the RAG path; the app still
   runs without it). Get one at https://aistudio.google.com/apikey. Easiest
   option — copy the example env file and fill it in; the app loads it
   automatically via python-dotenv:

   ```bash
   cp .env.example .env      # then edit .env and paste your key
   ```

   Or set it in your shell instead:

   ```bash
   export GEMINI_API_KEY=...      # Mac / Linux
   setx GEMINI_API_KEY "..."      # Windows (new shells)
   ```

---

## Running

**Streamlit UI (recommended):**

```bash
streamlit run src/app.py
```

**CLI (deterministic scorer):**

```bash
python -m src.main
```

**Tests** (no API key needed — the Gemini client is mocked):

```bash
pytest
```
