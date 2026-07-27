"""
Streamlit UI for the Music Recommender Simulation.

Run from the repo root:

    streamlit run src/app.py

The app has two entry points:
- **Describe your vibe** (RAG): free text -> Claude parses a profile -> the
  deterministic scorer retrieves songs -> Claude writes a grounded blurb.
- **Manual profile**: sliders/dropdowns that drive the deterministic scorer
  directly, with no LLM involved.

A side-by-side toggle shows the deterministic ranking next to the RAG result so
you can see how the language-understanding step changes what surfaces - the
biases documented in model_card.md, made visible.
"""

import logging
import os
import sys

# Ensure the repo root is importable so `src` resolves when Streamlit runs this
# file as a script (Streamlit only puts the script's own directory on sys.path).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from src.recommender import UserProfile, load_songs, recommend_songs
from src.rag import (
    DEFAULT_MODEL,
    catalog_vocab,
    has_api_key,
    load_env,
    recommend_with_rag,
)

logging.basicConfig(level=logging.INFO)
load_env()  # pick up ANTHROPIC_API_KEY from a repo-root .env if present

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "songs.csv"
)


@st.cache_data
def get_songs():
    return load_songs(DATA_PATH)


def render_retrieved(retrieved):
    """Show the retrieved songs with their deterministic scores and reasons."""
    for song, score, reasons in retrieved:
        st.markdown(f"**{song['title']}** — {song['artist']}  \nScore: `{score:.2f}`")
        st.caption(reasons)


def main() -> None:
    st.set_page_config(page_title="VibeMatch", page_icon="🎧", layout="centered")
    st.title("🎧 VibeMatch — Music Recommender")

    songs = get_songs()
    vocab = catalog_vocab(songs)

    with st.sidebar:
        st.header("Settings")
        model = st.text_input("Claude model", value=DEFAULT_MODEL)
        k = st.slider("How many songs to retrieve", 1, 10, 5)
        key_present = has_api_key()
        if key_present:
            st.success("ANTHROPIC_API_KEY detected — RAG enabled.")
        else:
            st.warning(
                "No ANTHROPIC_API_KEY found. The app still works — it falls "
                "back to the deterministic recommender (no AI text)."
            )
        st.caption(f"Catalog: {len(songs)} songs, "
                   f"{len(vocab['genres'])} genres, {len(vocab['moods'])} moods.")

    tab_rag, tab_manual = st.tabs(["Describe your vibe (RAG)", "Manual profile"])

    # --------------------------------------------------------------------- #
    # RAG tab
    # --------------------------------------------------------------------- #
    with tab_rag:
        st.write(
            "Describe what you want in plain language. Claude maps it onto the "
            "catalog's vocabulary, the scorer retrieves matches, and Claude "
            "explains the picks using only those songs."
        )
        query = st.text_input(
            "What are you in the mood for?",
            placeholder="something upbeat for a late-night drive, nothing aggressive",
        )
        compare = st.checkbox(
            "Show the raw deterministic ranking alongside the RAG result", value=True
        )

        if st.button("Recommend", type="primary") and query.strip():
            with st.spinner("Thinking..."):
                result = recommend_with_rag(
                    query.strip(), songs, k=k, model=model
                )

            if result.used_fallback:
                st.info(
                    "Ran in fallback mode (no key or an API call failed) — "
                    "results below are deterministic."
                )
            for warning in result.warnings:
                st.warning(warning)

            st.subheader("Recommendation")
            st.write(result.recommendation)

            with st.expander("How this was built (transparency)"):
                st.markdown(
                    f"- **Profile source:** {result.profile_source}\n"
                    f"- **Recommendation source:** {result.recommendation_source}\n"
                    f"- **Model:** {result.model or '—'}\n"
                    f"- **Token usage:** {result.usage or '—'}"
                )
                st.markdown("**Parsed profile**")
                st.json(_profile_to_dict(result.profile))
                st.markdown("**Retrieved songs**")
                render_retrieved(result.retrieved)
                st.markdown("**Pipeline log**")
                st.code("\n".join(result.logs))

            if compare:
                st.subheader("Raw deterministic ranking (no language understanding)")
                st.caption(
                    "Uses exact-string matching on your literal words — this is "
                    "the behavior the model card critiques."
                )
                raw_profile = _query_as_literal_profile(query.strip())
                raw = recommend_songs(raw_profile.to_prefs(), songs, k=k)
                render_retrieved(raw)

    # --------------------------------------------------------------------- #
    # Manual tab
    # --------------------------------------------------------------------- #
    with tab_manual:
        st.write("Drive the deterministic scorer directly — no AI involved.")
        genre = st.selectbox("Favorite genre", ["(any)"] + vocab["genres"])
        mood = st.selectbox("Favorite mood", ["(any)"] + vocab["moods"])
        energy = st.slider("Target energy", 0.0, 1.0, 0.5, 0.01)
        valence = st.slider("Target valence (positivity)", 0.0, 1.0, 0.5, 0.01)
        likes_acoustic = st.checkbox("Prefer acoustic songs")

        if st.button("Score songs"):
            profile = UserProfile(
                favorite_genre=None if genre == "(any)" else genre,
                favorite_mood=None if mood == "(any)" else mood,
                target_energy=energy,
                likes_acoustic=likes_acoustic,
                target_valence=valence,
            )
            results = recommend_songs(profile.to_prefs(), songs, k=k)
            st.subheader("Top matches")
            render_retrieved(results)


def _profile_to_dict(profile: UserProfile) -> dict:
    return {
        "favorite_genre": profile.favorite_genre,
        "favorite_mood": profile.favorite_mood,
        "target_energy": profile.target_energy,
        "target_valence": profile.target_valence,
        "likes_acoustic": profile.likes_acoustic,
    }


def _query_as_literal_profile(query: str) -> UserProfile:
    """Feed the raw query text straight into genre+mood (exact-string matching).

    This intentionally reproduces the old behavior for the comparison view: the
    literal phrase rarely matches a catalog label, so genre/mood usually score 0.
    """
    return UserProfile(
        favorite_genre=query,
        favorite_mood=query,
        target_energy=0.5,
        likes_acoustic=None,
    )


if __name__ == "__main__":
    main()
