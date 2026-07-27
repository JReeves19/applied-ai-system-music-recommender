"""
Retrieval-Augmented Generation (RAG) layer for the music recommender.

Pipeline
--------
1. **Understand** - a free-text request ("something upbeat for a late-night
   drive, nothing aggressive") is turned into a structured ``UserProfile`` by
   Claude, using catalog-derived enums so the parsed genre/mood are guaranteed
   to be vocabulary that actually exists in ``songs.csv``. This is the fix for
   the model card's "high-energy pop != pop" and "sad != melancholic" flaws.
2. **Retrieve** - the parsed profile is fed to the *existing, deterministic*
   ``recommend_songs`` scorer to pull the top-k candidate songs. The catalog is
   the knowledge base; the scorer is the retriever.
3. **Generate** - Claude writes a grounded, plain-language recommendation using
   *only* the retrieved songs' real attributes.

Guardrails
----------
- No ``ANTHROPIC_API_KEY`` / API error -> the whole thing degrades to the pure
  deterministic recommender, so the app and tests run with no key and no network.
- Anti-hallucination check: any catalog song Claude names must be in the
  retrieved set; otherwise it is flagged as a warning.
- Every stage is logged (query -> profile -> retrieved -> model -> usage).
"""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.recommender import UserProfile, recommend_songs

logger = logging.getLogger("music_recommender.rag")

DEFAULT_MODEL = "claude-sonnet-5"

# A scored, explained candidate: (song dict, score, reason string).
ScoredSong = Tuple[Dict[str, Any], float, str]


@dataclass
class RagResult:
    """Everything the UI (or a test) needs to inspect one RAG run."""
    query: str
    profile: UserProfile
    retrieved: List[ScoredSong]
    recommendation: str
    used_fallback: bool
    profile_source: str          # "llm" or "heuristic"
    recommendation_source: str   # "llm" or "deterministic"
    model: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Catalog helpers
# --------------------------------------------------------------------------- #
def catalog_vocab(songs: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Distinct genres and moods present in the catalog, sorted."""
    return {
        "genres": sorted({s["genre"] for s in songs}),
        "moods": sorted({s["mood"] for s in songs}),
    }


def _clamp01(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def load_env() -> bool:
    """Load a repo-root ``.env`` into the environment if python-dotenv is present.

    Safe to call more than once and safe when python-dotenv isn't installed
    (returns False rather than raising), so it never breaks the keyless path.
    Existing environment variables win over ``.env`` values.
    """
    try:
        from dotenv import load_dotenv  # noqa: WPS433 (optional dependency)
    except ImportError:
        return False
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return load_dotenv(os.path.join(repo_root, ".env"), override=False)


def has_api_key(api_key: Optional[str] = None) -> bool:
    """True when a usable API key is available (explicit or in the environment)."""
    return bool(api_key or os.environ.get("ANTHROPIC_API_KEY"))


# --------------------------------------------------------------------------- #
# Step 1 - understand: free text -> UserProfile
# --------------------------------------------------------------------------- #
def _profile_schema(vocab: Dict[str, List[str]]) -> Dict[str, Any]:
    """JSON schema for structured output; enums pin genre/mood to the catalog."""
    return {
        "type": "object",
        "properties": {
            "favorite_genre": {"type": ["string", "null"], "enum": vocab["genres"] + [None]},
            "favorite_mood": {"type": ["string", "null"], "enum": vocab["moods"] + [None]},
            "target_energy": {"type": ["number", "null"]},
            "target_valence": {"type": ["number", "null"]},
            "likes_acoustic": {"type": ["boolean", "null"]},
            "notes": {"type": "string"},
        },
        "required": [
            "favorite_genre",
            "favorite_mood",
            "target_energy",
            "target_valence",
            "likes_acoustic",
            "notes",
        ],
        "additionalProperties": False,
    }


def _parse_prompt(query: str, vocab: Dict[str, List[str]]) -> str:
    return (
        "Map the listener's request onto this catalog's vocabulary.\n\n"
        f"Available genres: {', '.join(vocab['genres'])}\n"
        f"Available moods: {', '.join(vocab['moods'])}\n\n"
        "Rules:\n"
        "- favorite_genre and favorite_mood MUST be one of the listed values, "
        "or null if nothing fits. Pick the closest match to the listener's "
        "intent (e.g. 'high-energy pop' -> 'pop', 'sad' -> 'melancholic').\n"
        "- target_energy and target_valence are 0.0-1.0 (energy = intensity, "
        "valence = musical positivity), or null if the request doesn't imply one.\n"
        "- likes_acoustic is true/false/null.\n"
        "- notes: one short sentence explaining your mapping.\n\n"
        f'Listener request: "{query}"'
    )


def parse_query_to_profile(
    client: Any,
    query: str,
    vocab: Dict[str, List[str]],
    model: str = DEFAULT_MODEL,
) -> Tuple[UserProfile, Dict[str, int], str]:
    """Call Claude to turn free text into a catalog-valid ``UserProfile``.

    Returns (profile, usage, notes). Raises on API error so the caller can
    decide to fall back.
    """
    response = client.messages.create(
        model=model,
        max_tokens=512,
        thinking={"type": "disabled"},
        system=(
            "You extract structured music-taste preferences from a listener's "
            "free-text request. You only ever use the catalog vocabulary given "
            "to you. You respond with the requested JSON and nothing else."
        ),
        messages=[{"role": "user", "content": _parse_prompt(query, vocab)}],
        output_config={"format": {"type": "json_schema", "schema": _profile_schema(vocab)}},
    )

    text = next((b.text for b in response.content if b.type == "text"), "{}")
    data = json.loads(text)

    profile = UserProfile(
        favorite_genre=data.get("favorite_genre"),
        favorite_mood=data.get("favorite_mood"),
        target_energy=_clamp01(data.get("target_energy")),
        likes_acoustic=data.get("likes_acoustic"),
        target_valence=_clamp01(data.get("target_valence")),
    )
    usage = _usage_dict(response)
    return profile, usage, data.get("notes", "")


def heuristic_profile(query: str, vocab: Dict[str, List[str]]) -> UserProfile:
    """Keyword fallback used when no LLM is available - keeps the app usable.

    Substring-matches catalog genres/moods against the request and guesses a
    couple of numeric signals from obvious words. Deliberately simple; it only
    has to give the deterministic scorer *something* to rank on.
    """
    q = query.lower()
    genre = next((g for g in vocab["genres"] if g.lower() in q), None)
    mood = next((m for m in vocab["moods"] if m.lower() in q), None)

    energy: Optional[float] = None
    if any(w in q for w in ("high energy", "high-energy", "energetic", "intense", "workout", "hype")):
        energy = 0.9
    elif any(w in q for w in ("chill", "calm", "relaxed", "mellow", "sleep", "study")):
        energy = 0.3

    likes_acoustic: Optional[bool] = None
    if "acoustic" in q:
        likes_acoustic = True
    elif "electronic" in q or "electric" in q:
        likes_acoustic = False

    return UserProfile(
        favorite_genre=genre,
        favorite_mood=mood,
        target_energy=energy,
        likes_acoustic=likes_acoustic,
    )


# --------------------------------------------------------------------------- #
# Step 3 - generate: retrieved songs -> grounded recommendation
# --------------------------------------------------------------------------- #
def _generation_prompt(query: str, retrieved: List[ScoredSong]) -> str:
    songs_payload = [
        {
            "title": song["title"],
            "artist": song["artist"],
            "genre": song["genre"],
            "mood": song["mood"],
            "energy": song["energy"],
            "valence": song["valence"],
            "acousticness": song["acousticness"],
            "match_score": round(score, 2),
            "match_reasons": reasons,
        }
        for song, score, reasons in retrieved
    ]
    return (
        "A listener asked for music. Below are the ONLY songs you may "
        "recommend - they were retrieved from the catalog by a scoring system. "
        "Do not mention or invent any song that is not in this list.\n\n"
        f"Listener request: \"{query}\"\n\n"
        f"Retrieved songs (JSON):\n{json.dumps(songs_payload, indent=2)}\n\n"
        "Write a short, friendly recommendation (a few sentences). Lead with "
        "your top pick, then briefly mention 1-2 alternatives. For each, say "
        "why it fits the request, grounding every claim in the song's listed "
        "attributes (genre, mood, energy, valence, acousticness). Be honest if "
        "a pick is only a partial fit."
    )


def generate_recommendation(
    client: Any,
    query: str,
    retrieved: List[ScoredSong],
    model: str = DEFAULT_MODEL,
) -> Tuple[str, Dict[str, int]]:
    """Call Claude to write a grounded blurb over the retrieved songs."""
    response = client.messages.create(
        model=model,
        max_tokens=700,
        thinking={"type": "disabled"},
        system=(
            "You are a music recommendation assistant. You recommend only from "
            "the songs provided in the user's message and ground every claim in "
            "their listed attributes. You never invent songs or attributes."
        ),
        messages=[{"role": "user", "content": _generation_prompt(query, retrieved)}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    return text, _usage_dict(response)


# --------------------------------------------------------------------------- #
# Guardrail + helpers
# --------------------------------------------------------------------------- #
def check_hallucination(
    recommendation: str,
    retrieved: List[ScoredSong],
    all_songs: List[Dict[str, Any]],
) -> List[str]:
    """Flag catalog songs named in the blurb that were NOT retrieved.

    Catches the realistic failure mode - the model reaching past the retrieved
    set into the rest of the catalog. Fully invented titles can't be detected
    generically, but grounding is enforced by the prompt.
    """
    text = recommendation.lower()
    retrieved_titles = {song["title"] for song, _s, _r in retrieved}
    warnings: List[str] = []
    for song in all_songs:
        title = song["title"]
        if title in retrieved_titles:
            continue
        if title.lower() in text:
            warnings.append(
                f"Recommendation named '{title}', which was not in the retrieved set."
            )
    return warnings


def _usage_dict(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {}
    return {
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    }


def _deterministic_blurb(retrieved: List[ScoredSong]) -> str:
    if not retrieved:
        return "No songs matched that request."
    lines = ["Top matches from the catalog (scored deterministically):"]
    for song, score, reasons in retrieved:
        lines.append(
            f"- {song['title']} by {song['artist']} "
            f"(score {score:.2f}) - {reasons}"
        )
    return "\n".join(lines)


def build_client(api_key: Optional[str] = None) -> Any:
    """Construct an Anthropic client (imported lazily so the SDK is optional)."""
    import anthropic  # noqa: WPS433 (intentional lazy import)

    return anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def recommend_with_rag(
    query: str,
    songs: List[Dict[str, Any]],
    k: int = 5,
    api_key: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    client: Any = None,
) -> RagResult:
    """Run the full parse -> retrieve -> generate pipeline with graceful fallback.

    ``client`` can be injected (used by tests); otherwise one is built from the
    API key / environment. If no key is available or any API call fails, the
    result degrades to the deterministic recommender and ``used_fallback`` is set.
    """
    vocab = catalog_vocab(songs)
    logs: List[str] = [f"query: {query!r}"]
    warnings: List[str] = []
    usage: Dict[str, int] = {}

    can_call_llm = client is not None or has_api_key(api_key)

    # ---- Step 1: understand -------------------------------------------------
    profile: UserProfile
    profile_source = "heuristic"
    if can_call_llm:
        try:
            if client is None:
                client = build_client(api_key)
            profile, parse_usage, notes = parse_query_to_profile(client, query, vocab, model)
            profile_source = "llm"
            usage = _merge_usage(usage, parse_usage)
            logs.append(f"parsed profile via {model}: {profile} ({notes})")
        except Exception as exc:  # noqa: BLE001 - any failure means fall back
            logger.warning("Query parsing failed, using heuristic profile: %s", exc)
            warnings.append(f"Query understanding failed ({exc}); used keyword fallback.")
            profile = heuristic_profile(query, vocab)
            logs.append(f"heuristic profile: {profile}")
            can_call_llm = False  # don't try the generation call either
    else:
        profile = heuristic_profile(query, vocab)
        logs.append(f"no API key; heuristic profile: {profile}")

    # ---- Step 2: retrieve (always deterministic) ----------------------------
    retrieved = recommend_songs(profile.to_prefs(), songs, k=k)
    logs.append("retrieved: " + ", ".join(f"{s['title']} ({sc:.2f})" for s, sc, _ in retrieved))

    # ---- Step 3: generate ---------------------------------------------------
    recommendation_source = "deterministic"
    if can_call_llm:
        try:
            recommendation, gen_usage = generate_recommendation(client, query, retrieved, model)
            recommendation_source = "llm"
            usage = _merge_usage(usage, gen_usage)
            warnings.extend(check_hallucination(recommendation, retrieved, songs))
            logs.append(f"generated recommendation via {model} ({usage})")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Generation failed, using deterministic blurb: %s", exc)
            warnings.append(f"Generation failed ({exc}); showing deterministic results.")
            recommendation = _deterministic_blurb(retrieved)
    else:
        recommendation = _deterministic_blurb(retrieved)

    used_fallback = profile_source != "llm" or recommendation_source != "llm"

    return RagResult(
        query=query,
        profile=profile,
        retrieved=retrieved,
        recommendation=recommendation,
        used_fallback=used_fallback,
        profile_source=profile_source,
        recommendation_source=recommendation_source,
        model=model if not used_fallback else (model if profile_source == "llm" else None),
        usage=usage,
        warnings=warnings,
        logs=logs,
    )


def _merge_usage(a: Dict[str, int], b: Dict[str, int]) -> Dict[str, int]:
    out = dict(a)
    for key, value in b.items():
        out[key] = out.get(key, 0) + value
    return out
