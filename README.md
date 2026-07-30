# 🎧 Music Recommender Simulation — with RAG + Streamlit

A content-based music recommender that turns a listener's taste into ranked, **explainable** song recommendations. Every pick comes with the exact reasons it scored well, and a Retrieval-Augmented Generation (RAG) layer lets you ask for music in natural language ("something upbeat for a late-night drive, nothing aggressive") instead of filling out a form.

**Why it matters:** recommenders quietly shape what millions of people listen to, and most are black boxes. This project is a small, fully transparent one; you can see the score, the reasons, and even a side-by-side view of how language understanding changes the results, which makes it a concrete way to study where recommender bias comes from.

---

## Original project

This builds on my **Music Recommender Simulation** from Module 3. The original was a content-based recommender: it represented songs and a user "taste profile" as data, then used a hand-designed weighted scoring rule (mood, genre, energy, valence, acousticness) to rank songs and explain each recommendation. Its goals were to turn taste data into predictions, evaluate what the system got right and wrong, and reflect on how it mirrors real-world AI recommenders. It ran only as a CLI over a small CSV catalog and matched genre/mood by **exact string**, which is the main limitation this upgrade set out to fix.

---

## What's new

### 1. RAG feature (the advanced AI feature)

The original recommender matched a profile with **exact-string** genre/mood comparisons, so `"high-energy pop"` never matched the catalog's `"pop"`, and `"sad"` never matched `"melancholic"` (documented in the model card). RAG fixes exactly that, in three stages:

1. **Understand** — Gemini (`gemini-3.5-flash-lite`) parses a free-text request into a structured `UserProfile`, using **catalog-derived enums** so the parsed genre/mood are guaranteed to be vocabulary that exists in `songs.csv`.
2. **Retrieve** — that profile is fed to the **existing deterministic scorer** (`score_song` / `recommend_songs`) to pull the top-*k* candidate songs. The catalog is the knowledge base; the scorer is the retriever.
3. **Generate** — Gemini writes a grounded, plain-language recommendation using **only** the retrieved songs' real attributes.

The retrieved songs are what Gemini reasons over — the AI actively uses the retrieved data to form its answer, rather than printing it alongside a canned response.

**Guardrails, logging, and reliability:**
- If `GEMINI_API_KEY` is missing or an API call fails, the app **degrades gracefully** to the pure deterministic recommender (a keyword heuristic builds the profile). The app and the tests run with no key and no network.
- **Anti-hallucination check:** any catalog song Gemini names that wasn't retrieved is flagged as a warning.
- Every stage is logged (query → parsed profile → retrieved songs → model → token usage), surfaced in the UI's transparency panel.

### 2. Streamlit UI

- **Describe your vibe (RAG):** free-text box → parsed profile → retrieved songs → grounded recommendation.
- **Manual profile:** sliders/dropdowns that drive the deterministic scorer directly (no LLM).
- **Deterministic-vs-RAG comparison** toggle that shows the raw exact-string ranking next to the RAG result — making the model card's biases visible.

### 3. Bigger catalog

The dataset grew from **18 to 30 songs**, specifically adding second entries for genres/moods that previously had only one, and filling a gap in medium-energy songs (nothing used to sit between 0.55 and 0.74 energy).

### 4. Cleanup

The `Recommender` class and `score_song`/`recommend_songs` functions were two parallel, inconsistent code paths (the class methods were unimplemented stubs that passed the starter tests by accident). They're now unified: `score_song` is the single scoring implementation, and `Recommender` delegates to it, so the OOP and functional APIs can never drift apart. `UserProfile` gained a `target_valence` field and a `to_prefs()` adapter.

---

## Architecture overview

The full system diagram is in [`diagrams/architecture.mmd`](diagrams/architecture.mmd) (Mermaid — view it on [mermaid.live](https://mermaid.live) or with a Mermaid-enabled Markdown preview).

Data flows **input → understand → retrieve → generate → guardrails → output**:

- **Input** — a free-text request (RAG tab) or a manual profile (sliders), entered in the Streamlit UI.
- **Understand (agent)** — Gemini maps free text onto catalog-valid genres/moods and numeric targets, producing a `UserProfile`. (Skipped on the manual path.)
- **Retrieve (retriever)** — the deterministic scorer ranks the 30-song catalog (`data/songs.csv`, the knowledge base) against that profile and returns the top-*k* with scores and reasons.
- **Generate (agent)** — Gemini writes a grounded blurb using only the retrieved songs.
- **Guardrails** — a decision point routes to the deterministic fallback when there's no key or an API error, and an anti-hallucination check verifies the blurb only names retrieved songs. Every stage is logged.
- **Output** — the recommendation, a transparency panel (parsed profile, retrieved songs, token usage), and the deterministic-vs-RAG comparison.
- **Humans & testing** — a human sets the API key and reviews the transparency panel; `pytest` (with a mocked Gemini client) verifies the scorer, pipeline, fallback, and guardrail.

**File layout:**

```
data/songs.csv                 # 30-song catalog (the knowledge base)
src/recommender.py             # deterministic core: Song, UserProfile, score_song, Recommender
src/rag.py                     # RAG layer: parse -> retrieve -> generate, guardrails, fallback
src/app.py                     # Streamlit UI
src/main.py                    # CLI runner
src/list_models.py             # helper: list Gemini models your key can access
tests/test_recommender.py      # scoring + OOP/functional parity
tests/test_rag.py              # RAG pipeline with a mocked Gemini client
diagrams/architecture.mmd      # system diagram (Mermaid)
model_card.md                  # responsible-AI reflection, bias analysis, limitations
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

3. Set your Gemini API key (required only for the RAG path; the app still runs without it). Get one at https://aistudio.google.com/apikey. Easiest option — copy the example env file and fill it in; the app loads it automatically via python-dotenv:

   ```bash
   cp .env.example .env      # then edit .env and paste your key
   ```

   Or set it in your shell instead:

   ```bash
   export GEMINI_API_KEY=...      # Mac / Linux
   setx GEMINI_API_KEY "..."      # Windows (new shells)
   ```

   If `gemini-3.5-flash-lite` isn't available to your key, run `python -m src.list_models` to see what is, then change the model in the app's sidebar.

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

---

## Sample interactions

### Example 1 — RAG, natural language (real `gemini-3.5-flash-lite` run)

**Input:** `something upbeat for late-night drive, nothing aggressive`

**Parsed profile:** genre `synthwave`, target energy ≈ 0.80, avoids aggressive moods.

**AI output:**
> For your late-night drive, my top pick is **"Night Drive Loop"** by Neon Echo. It fits well because its synthwave genre matches your late-night setting, and it brings a solid energy level of 0.75 (close to the target 0.80) while avoiding anything too aggressive… If you want a couple of alternatives, you could check out **"Glass Elevator"** by Cassette Ghost, another synthwave track with an energy of 0.62, a sultry mood, a valence of 0.52, and an acousticness of 0.21. Alternatively, there is **"Midnight Coding"** by LoRoom; while it has a chill mood and a lower energy of 0.42 (making it less upbeat), it aligns with an acousticness of 0.71 and a valence of 0.56.

*(LLM wording varies run to run; the retrieved songs and scores underneath it are deterministic.)*

### Example 2 — Manual profile (deterministic, no LLM)

**Input:** genre `lofi`, mood `chill`, target energy `0.40`, target valence `0.55`, likes acoustic ✓

**Output (top 3):**
```
Library Rain      9.66  mood matched (chill); genre matched (lofi); energy close: 0.35 vs 0.40; valence close: 0.60 vs 0.55; acousticness aligned (0.86)
Midnight Coding   9.65  mood matched (chill); genre matched (lofi); energy close: 0.42 vs 0.40; valence close: 0.56 vs 0.55; acousticness aligned (0.71)
Spacewalk Thoughts 7.48 mood matched (chill); energy close: 0.28 vs 0.40; valence close: 0.65 vs 0.55; acousticness aligned (0.92)
```

### Example 3 — Fallback with no API key (graceful degradation)

**Input:** `an intense rock workout track` (run with no `GEMINI_API_KEY`)

The app can't call Gemini, so a keyword heuristic builds the profile (genre `rock`, mood `intense`, energy `0.90`) and the deterministic scorer takes over — no crash, no AI text.

**Output (top 3):**
```
Storm Runner    6.98  mood matched (intense); genre matched (rock); energy close: 0.91 vs 0.90
Gym Hero        4.94  mood matched (intense); energy close: 0.93 vs 0.90
Highway Signal  3.60  genre matched (rock); energy close: 0.70 vs 0.90
```

---

## Design decisions & trade-offs

- **Keep the original scorer as the retriever.** Rather than replace my hand-built scoring rule with an LLM, RAG wraps around it: Gemini only translates language into the scorer's vocabulary, and my deterministic code still does all the ranking. **Trade-off:** recommendations stay explainable and reproducible, but they can never go beyond content matching (no collaborative "people like you also liked…" surprises).
- **Constrain the LLM to catalog enums.** The parse step forces genre/mood to values that exist in `songs.csv`, which is what fixes the exact-string problem. **Trade-off:** the model can't invent a genre, but it may map an ambiguous phrase to a debatable label — a new, harder-to-inspect source of bias (see the model card).
- **Deterministic fallback over hard failure.** No key or an API error degrades to the pure scorer instead of erroring out. **Trade-off:** the app always works and tests never touch the network, but the fallback profile (keyword heuristic) is much blunter than the LLM's.
- **Prompt + verification for grounding, not just trust.** The generation prompt says "only these songs," and a post-check flags any catalog song named but not retrieved. **Trade-off:** it catches the realistic failure (reaching past the retrieved set) but can't detect a fully invented title.
- **Gemini via `google-genai`.** The project originally targeted Claude; it was swapped to Gemini because that's the API key I have. All LLM calls are isolated in `src/rag.py`, so the provider swap touched one file.

---

## Testing summary

**What I test.** `pytest` runs 15 tests with **no API key and no network** — the Gemini client is mocked:
- `tests/test_recommender.py` — scoring correctness (exact expected totals), that unset preferences don't contribute, and that the OOP `Recommender` and functional `recommend_songs` produce identical rankings.
- `tests/test_rag.py` — the full parse→retrieve→generate happy path, the no-key fallback, the API-error fallback, the anti-hallucination guardrail, and the keyword heuristic.

**What worked.** The mocked-client design means the whole RAG pipeline is testable offline, and the fallback path is exercised directly. Unifying the two scoring code paths was validated by a parity test.

**What didn't (and how I handled it).** The starter tests were passing against **unimplemented stub methods** — a false green that the cleanup fixed. The default model `gemini-2.5-flash` also returned a 404 (retired for new keys); the app's fallback caught it cleanly and I switched to a current model. The one thing tests **can't** cover is the live LLM's exact wording, which is non-deterministic — so I verify that manually by running the Streamlit app with my key.

**What I learned.** Testing an AI feature is mostly about isolating the non-deterministic part (the model call) behind a seam you can fake, so everything around it stays deterministic and fast.

---

## Reflection

Building this taught me that adding an LLM doesn't remove bias; it moves it. The exact-string flaw got fixed, but the fix relocated a judgment call ("what does *upbeat* mean?") from my visible scoring rule into an opaque model decision. Keeping the deterministic scorer in charge, and building a comparison view that shows both, was what let me actually see that shift instead of just trusting the AI.

📄 **The full responsible-AI reflection** — how I collaborated with AI, one helpful and one flawed AI suggestion, bias analysis, and the system's limitations — is in [`model_card.md`](model_card.md).
