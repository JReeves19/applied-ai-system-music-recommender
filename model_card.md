# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  
 
**VibeMatch 1.0**

---

## 2. Intended Use  
  
This model picks songs from a small catalog based on what a listener says they like. It looks at genre, mood, energy, and a few other traits. It assumes the listener describes their taste using simple, exact words, like "happy" or "pop." It's meant to show how a basic recommender works, including its rough edges.

---

## 3. How the Model Works  

Each song has some tags, like genre and mood. Each song also has some numbers, like how energetic it is, how happy it sounds, and how acoustic it is. The listener tells the model what they like: a favorite genre, a favorite mood, a target energy level, and whether they like acoustic songs. The model checks each song against those preferences and hands out points. A mood match is worth the most points. A genre match is worth a bit less. Energy and happiness (valence) earn points based on how close they are to the target, not just a yes-or-no match. Liking acoustic songs earns a smaller number of points. All the points get added together into one score per song. The model sorts every song by score and shows the top few, along with the reasons it picked them. When I started, the scoring functions were empty placeholders. I wrote the actual point system myself.

---

## 4. Data  

The catalog now has 30 songs, expanded from an original 18. There are 15 different genres, like pop, lofi, rock, jazz, and hip hop, and 15 different moods, like happy, chill, intense, and melancholic. I deliberately added the 12 new songs to fix two problems the original dataset had: most genres and moods appeared on only one song each, and there was a gap in energy levels with nothing between 0.55 and 0.74. After the expansion, only one genre (`classical`) still has a single song, the mid-energy range is well covered, and most moods have at least two songs — though a few moods (`aggressive`, `bittersweet`, `melancholic`, `romantic`) are still represented by a single song, so some niche tastes remain thin.

*Note: the experiments and limitations described in Sections 6 and 7 were run on the original 18-song catalog, before this expansion, so their specific counts (e.g. "11 of 14 moods on a single song") describe that earlier version.*

---

## 5. Strengths    

The model does well with common tastes, like "happy pop" or "chill lofi." Those categories have more than one matching song, so the model can actually compare options and pick a real winner. The energy-matching math works the way I'd expect: the closer a song's energy is to the target, the higher it scores. I checked this by hand and the numbers lined up every time. The model also explains itself well. It always tells you why a song was picked, which makes it easy to spot when something looks off.

---

## 6. Limitations and Bias 

One weakness I found is that mood and genre matching is all-or-nothing: a song only earns points if its mood or genre string is an exact match to the user's preference, with no partial credit for similar tastes. When I counted the categories in my 18-song catalog, 11 of the 14 moods and 12 of the 14 genres appear on only a single song, meaning a user who prefers a mood like "sultry" or "peaceful" has exactly one song in the whole catalog that can ever earn the +3 mood bonus. If that song scores poorly on energy or valence, the user gets no benefit from stating their mood preference at all. This showed up clearly when I temporarily disabled the mood check to test sensitivity: my top recommendation for an "intense, high-energy" profile changed completely, revealing that the +3 mood bonus (a bigger single swing than the entire energy score's usable range) was doing most of the work in the ranking rather than a balanced blend of features. Users with mainstream tastes (moods/genres with multiple catalog matches, like "happy" or "chill") get richer, better-differentiated recommendations, while users with niche or simply differently-worded preferences (e.g., "sad" instead of "melancholic") are silently treated the same as users who specified no preference at all.
---

## 7. Evaluation  

I tested four different listener profiles: a baseline "pop, happy, energy 0.8" listener, a "chill lofi, energy 0.40" listener, a "high-energy pop, happy, energy 0.85" listener, and a "deep intense rock, energy 0.95" listener. For each one, I looked at whether the top 5 songs actually matched the feeling the profile described, not just the numbers.

The most surprising result came from the "high-energy pop, happy" listener. I expected the top results to be upbeat, happy-sounding pop songs, since that's exactly what the profile asked for. Instead, "Gym Hero" — a song tagged as "intense," not "happy" — showed up in the top 5. Here's why: the listener typed "High-energy pop" as their genre, but that exact phrase doesn't match any genre actually in my catalog (songs are labeled just "pop," "indie pop," and so on), so the genre points never got awarded to anyone. On top of that, only two songs in my whole catalog are tagged "happy," so once those two were picked, the recommender had three more slots to fill and no more "happy" songs to fill them with. It filled the gap with whatever songs happened to be closest in energy level to 0.85 — and "Gym Hero," despite being an "intense" song, happens to sit at almost exactly that energy level. In other words, the system quietly swapped "find me the right vibe" for "find me the right speed" once it ran out of true mood matches, without ever telling the listener that's what it was doing. That was the clearest sign to me that the recommender leans much more heavily on energy as a fallback than I originally realized, and that a listener typing natural phrases like "high-energy pop" instead of the exact catalog words can end up with recommendations that technically score well but don't feel like what they asked for.

---

## 8. Future Work  

**Already improved since the first version:** I expanded the catalog from 18 to 30 songs, specifically adding second entries for genres and moods that previously had only one, and filling the medium-energy gap (0.55–0.74) that had left mid-tempo listeners with few options.

**Still on my list:** I'd add fuzzy matching so words like "sad" and "melancholic" count as close enough. I'd give partial credit for similar genres, like "pop" and "indie pop." I'd lower the mood and genre bonus a little so energy and valence matter more too. And I'd tell the listener when their genre or mood doesn't match anything in the catalog, instead of silently scoring it as zero.

---

## 9. Personal Reflection  

This project showed me that "correct" math can still produce biased results. The scoring logic wasn't buggy, but the data behind it was uneven, and that uneven data shaped every recommendation. I was surprised how much one flat bonus, the mood match, could dominate the whole ranking. Testing with weird or conflicting profiles, and turning parts of the code on and off, taught me more than just reading the code ever could. Now when I use a real music app, I think differently about why certain songs keep showing up for me.

---

## 10. Update: RAG Improvement

After the core project, I added a **Retrieval-Augmented Generation (RAG)** feature to directly attack the biggest weakness this model card identified: exact-string matching. Sections 6 and 7 showed that a listener who typed "high-energy pop" or "sad" got no credit, because those exact strings aren't in the catalog (`pop`, `melancholic`).

**How it works now.** A listener types a request in plain language. The system runs three stages:

1. **Understand.** Gemini (`gemini-3.5-flash-lite`) reads the free text and produces a structured taste profile, but it's constrained to choose only from the genres and moods that actually exist in the catalog. This is what fixes the exact-match problem: "high-energy pop" now maps to `pop`, and "sad" maps to `melancholic`.
2. **Retrieve.** That profile is handed to my *original* scoring function (the same 3/2/2/2/1 algorithm). My work still does the ranking — the LLM only translates the request into terms my scorer understands.
3. **Generate.** Gemini writes a short, plain-language recommendation, but it may only mention songs that were retrieved, and it has to justify each pick using that song's real attributes.

**How this addresses the documented bias.** The exact-string penalty from Section 6 is gone for natural-language input, because the understanding step normalizes phrasing to catalog vocabulary before scoring. The "silent fallback to energy" problem from Section 7 is also softened: the generation step has to *explain* why a song was picked, so a mismatch is now visible in the text instead of hidden.

**New biases and limitations the RAG layer introduces.**
- **The catalog is still tiny and uneven.** RAG maps words better, but it can't invent songs. A niche mood with one catalog song still has one option — the underlying data imbalance is unchanged.
- **The LLM is a new source of bias.** Which catalog word Gemini maps a phrase to is now a model judgment, not a rule I can fully inspect. "Chill" might map to `chill`, `relaxed`, or `peaceful` depending on the model.
- **Cost, latency, and reproducibility.** RAG needs an API key and network, and its wording varies run to run. To keep the project reproducible, I built a guardrail: with no key or on any API error, the app falls back to the pure deterministic recommender, and all tests mock the model so they never call the network.
- **Grounding is enforced but not perfect.** I check that any *catalog* song named in the output was actually retrieved, but a fully invented title can't be caught by that check alone — the prompt is the main defense there.

---

## 11. Reflection and Ethics

This section thinks critically about the responsible-AI side of the project. (Sections 6, 7, and 10 have the deeper detail; here I answer the four reflection questions directly.)

### What are the limitations or biases in your system?

There are three layers of bias, and adding AI moved the problem rather than removing it:

- **Designer bias (the weights).** The 3/2/2/2/1 point split is my own judgment, not learned from real listeners. The +3 mood bonus is a bigger single swing than the entire usable energy range, so mood quietly dominates the ranking (see Section 6).
- **Data bias (the catalog).** With 30 songs, common tastes ("happy pop," "chill lofi") have several matches and get well-differentiated results, while niche moods (`aggressive`, `bittersweet`, `melancholic`, `romantic`) still have exactly one song each, so those listeners get thin, sometimes arbitrary results. Being content-based only, the system also can never surprise someone with a song outside their stated taste (a filter-bubble tendency).
- **Model bias (the new LLM layer).** RAG fixed the exact-string penalty, but which catalog word Gemini maps a phrase to ("chill" -> `chill` vs `relaxed` vs `peaceful`) is now an opaque model judgment I can't fully inspect, and it can vary run to run. I traded a transparent-but-rigid rule for a flexible-but-less-inspectable one.

### Could your AI be misused, and how would you prevent that?

It's a low-stakes music simulator, but a few realistic misuse paths exist, and most are already mitigated:

- **Treating the output as objective.** The recommendation reads authoritative ("here's why this fits"), which could lull a user into trusting subjective, hand-tuned weights as fact, the same "automation bias" that lets real platforms hide payola-style promotion behind a neutral-looking algorithm. **Mitigation:** the transparency panel and per-song reasons expose *exactly* why each song ranked, and the deterministic-vs-RAG comparison shows the ranking is a designed choice, not ground truth.
- **Abusing the free-text box (prompt injection / offensive output).** A user could try to make the model emit arbitrary or unsafe text since the output is shown in the UI. **Mitigation:** the model only ever sees the query plus the retrieved songs, has no tools or secrets, and its output is only displayed, never executed; generation is constrained to retrieved catalog songs and checked by the anti-hallucination guardrail. **Would add:** input-length and rate limits and a content filter on the box.
- **API-key / cost abuse.** A leaked key could run up charges. **Mitigation:** the key lives in `.env`, which is gitignored and never committed.

### What surprised you while testing your AI's reliability?

Two things stood out, both about external reliability that unit tests can't see:

- **A "current" model can vanish.** My default model `gemini-2.5-flash` returned a live **404 — "no longer available to new users."** The mocked tests were all green, yet the real app couldn't call the model. It surprised me that a hard-coded model ID is itself a reliability risk — and reassured me that the graceful fallback caught it cleanly (the app degraded to the deterministic recommender instead of crashing).
- **Green tests can be meaningless.** The original starter tests passed against `Recommender` methods that were actually **unimplemented stubs** (a false "green"). It drove home that a passing suite only proves what it actually exercises, which is why I added scoring-correctness and OOP/functional parity tests.

### Describe your collaboration with AI (one helpful, one flawed suggestion)

I built the RAG + Streamlit upgrade using an AI coding agent (Claude Code), giving it high-level goals and reviewing its work at each step. (A fuller log is in `ai_interactions.md`.)

- **One helpful suggestion.** While reading my code, the agent flagged something I'd missed: my `Recommender` class methods were placeholder stubs, so the starter tests were passing by accident. It unified the duplicated scoring paths (`score_song` as the single source of truth) and added real tests to prove it(a correctness problem I would not have caught on my own).
- **One flawed suggestion.** The agent's initial default model, `gemini-2.5-flash`, was **wrong** — that model is retired for new keys, and it only failed when I ran the app live with my own key. I had to correct it by switching to a current model. The lesson: AI suggestions about fast-moving external details (model names, API shapes) need live verification, not just passing tests. The AI's "known" model was out of date.
