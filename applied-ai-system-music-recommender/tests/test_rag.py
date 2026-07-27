"""Tests for the RAG layer.

The Anthropic client is faked, so these tests need no API key and make no
network calls. They cover the happy path (parse -> retrieve -> generate), the
no-key fallback, the API-error fallback, the anti-hallucination guardrail, and
the keyword heuristic.
"""

import json
import os

import pytest

from src.recommender import load_songs
from src.rag import (
    catalog_vocab,
    check_hallucination,
    heuristic_profile,
    parse_query_to_profile,
    recommend_with_rag,
)

DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "songs.csv"
)


@pytest.fixture
def songs():
    return load_songs(DATA_PATH)


# --------------------------------------------------------------------------- #
# Fake Anthropic client
# --------------------------------------------------------------------------- #
class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeUsage:
    input_tokens = 12
    output_tokens = 7


class _FakeResponse:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, parse_text, gen_text, fail=False):
        self._parse_text = parse_text
        self._gen_text = gen_text
        self._fail = fail

    def create(self, **kwargs):
        if self._fail:
            raise RuntimeError("simulated API error")
        # The parse call is the one that requests structured output.
        if "output_config" in kwargs:
            return _FakeResponse(self._parse_text)
        return _FakeResponse(self._gen_text)


class FakeClient:
    def __init__(self, parse_text, gen_text, fail=False):
        self.messages = _FakeMessages(parse_text, gen_text, fail=fail)


def _profile_json(**overrides):
    data = {
        "favorite_genre": "pop",
        "favorite_mood": "happy",
        "target_energy": 0.8,
        "target_valence": None,
        "likes_acoustic": None,
        "notes": "mapped 'upbeat pop' onto pop/happy",
    }
    data.update(overrides)
    return json.dumps(data)


# --------------------------------------------------------------------------- #
# parse_query_to_profile
# --------------------------------------------------------------------------- #
def test_parse_maps_free_text_to_catalog_profile(songs):
    client = FakeClient(parse_text=_profile_json(), gen_text="")
    profile, usage, notes = parse_query_to_profile(client, "upbeat pop", catalog_vocab(songs))
    assert profile.favorite_genre == "pop"
    assert profile.favorite_mood == "happy"
    assert profile.target_energy == 0.8
    assert usage["input_tokens"] == 12
    assert "pop" in notes


def test_parse_clamps_out_of_range_numbers(songs):
    client = FakeClient(parse_text=_profile_json(target_energy=1.7, target_valence=-0.3), gen_text="")
    profile, _usage, _notes = parse_query_to_profile(client, "x", catalog_vocab(songs))
    assert profile.target_energy == 1.0
    assert profile.target_valence == 0.0


# --------------------------------------------------------------------------- #
# recommend_with_rag - happy path
# --------------------------------------------------------------------------- #
def test_rag_happy_path_uses_llm(songs):
    client = FakeClient(
        parse_text=_profile_json(),
        gen_text="My top pick is Sunrise City, an upbeat happy pop track.",
    )
    result = recommend_with_rag("upbeat happy pop", songs, k=3, client=client)
    assert result.profile_source == "llm"
    assert result.recommendation_source == "llm"
    assert result.used_fallback is False
    assert result.warnings == []
    # Retrieval is deterministic and should surface the pop/happy track first.
    assert result.retrieved[0][0]["title"] == "Sunrise City"
    assert result.usage["input_tokens"] > 0


# --------------------------------------------------------------------------- #
# recommend_with_rag - fallbacks
# --------------------------------------------------------------------------- #
def test_rag_falls_back_without_api_key(songs, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = recommend_with_rag("chill lofi", songs, k=3)  # no client, no key
    assert result.used_fallback is True
    assert result.profile_source == "heuristic"
    assert result.recommendation_source == "deterministic"
    # Heuristic still picks up "lofi" and "chill" from the query.
    assert result.profile.favorite_genre == "lofi"
    assert result.profile.favorite_mood == "chill"
    assert len(result.retrieved) == 3


def test_rag_falls_back_on_api_error(songs):
    client = FakeClient(parse_text="", gen_text="", fail=True)
    result = recommend_with_rag("anything", songs, k=2, client=client)
    assert result.used_fallback is True
    assert result.profile_source == "heuristic"
    assert any("failed" in w.lower() for w in result.warnings)


# --------------------------------------------------------------------------- #
# Guardrail + heuristic
# --------------------------------------------------------------------------- #
def test_check_hallucination_flags_non_retrieved_catalog_song(songs):
    retrieved = [(songs[0], 5.0, "reason")]  # only Sunrise City retrieved
    other_title = songs[1]["title"]  # a real catalog song NOT retrieved
    text = f"You should listen to {other_title}."
    warnings = check_hallucination(text, retrieved, songs)
    assert any(other_title in w for w in warnings)


def test_check_hallucination_silent_when_grounded(songs):
    retrieved = [(songs[0], 5.0, "reason")]
    text = f"Great pick: {songs[0]['title']}."
    assert check_hallucination(text, retrieved, songs) == []


def test_heuristic_profile_reads_keywords(songs):
    vocab = catalog_vocab(songs)
    profile = heuristic_profile("I want an intense rock workout track", vocab)
    assert profile.favorite_genre == "rock"
    assert profile.target_energy == 0.9
