from src.recommender import (
    Song,
    UserProfile,
    Recommender,
    score_song,
    recommend_songs,
)

def make_small_recommender() -> Recommender:
    songs = [
        Song(
            id=1,
            title="Test Pop Track",
            artist="Test Artist",
            genre="pop",
            mood="happy",
            energy=0.8,
            tempo_bpm=120,
            valence=0.9,
            danceability=0.8,
            acousticness=0.2,
        ),
        Song(
            id=2,
            title="Chill Lofi Loop",
            artist="Test Artist",
            genre="lofi",
            mood="chill",
            energy=0.4,
            tempo_bpm=80,
            valence=0.6,
            danceability=0.5,
            acousticness=0.9,
        ),
    ]
    return Recommender(songs)


def test_recommend_returns_songs_sorted_by_score():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    results = rec.recommend(user, k=2)

    assert len(results) == 2
    # Starter expectation: the pop, happy, high energy song should score higher
    assert results[0].genre == "pop"
    assert results[0].mood == "happy"


def test_explain_recommendation_returns_non_empty_string():
    user = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
    )
    rec = make_small_recommender()
    song = rec.songs[0]

    explanation = rec.explain_recommendation(user, song)
    assert isinstance(explanation, str)
    assert explanation.strip() != ""


# --------------------------------------------------------------------------- #
# Scoring correctness (the algorithm is now the single source of truth)
# --------------------------------------------------------------------------- #
def test_score_song_computes_expected_total():
    song = {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.80,
        "valence": 0.90,
        "acousticness": 0.20,
    }
    prefs = {
        "genre": "pop",
        "mood": "happy",
        "energy": 0.80,
        "valence": 0.90,
        "likes_acoustic": False,
    }
    # 3 (mood) + 2 (genre) + 2 (energy exact) + 2 (valence exact) + 0.8 (1-0.2)
    score, reasons = score_song(prefs, song)
    assert score == 9.8
    assert len(reasons) == 5


def test_unset_preferences_do_not_contribute():
    song = {"genre": "pop", "mood": "happy", "energy": 0.5, "valence": 0.5, "acousticness": 0.5}
    # Empty prefs -> nothing fires, score is zero.
    score, reasons = score_song({}, song)
    assert score == 0.0
    assert reasons == []


def test_to_prefs_omits_unset_valence():
    profile = UserProfile(
        favorite_genre="pop", favorite_mood="happy", target_energy=0.8, likes_acoustic=False
    )
    prefs = profile.to_prefs()
    assert "valence" not in prefs  # target_valence was never set

    profile_with_valence = UserProfile(
        favorite_genre="pop",
        favorite_mood="happy",
        target_energy=0.8,
        likes_acoustic=False,
        target_valence=0.7,
    )
    assert profile_with_valence.to_prefs()["valence"] == 0.7


def test_class_and_functional_paths_agree():
    """The OOP Recommender and recommend_songs must produce the same ranking."""
    rec = make_small_recommender()
    user = UserProfile(
        favorite_genre="pop", favorite_mood="happy", target_energy=0.8, likes_acoustic=False
    )
    class_order = [s.title for s in rec.recommend(user, k=2)]

    song_dicts = [
        {
            "id": s.id, "title": s.title, "artist": s.artist, "genre": s.genre,
            "mood": s.mood, "energy": s.energy, "tempo_bpm": s.tempo_bpm,
            "valence": s.valence, "danceability": s.danceability,
            "acousticness": s.acousticness,
        }
        for s in rec.songs
    ]
    func_order = [s["title"] for s, _score, _r in recommend_songs(user.to_prefs(), song_dicts, k=2)]

    assert class_order == func_order


def test_recommend_respects_k():
    rec = make_small_recommender()
    user = UserProfile(
        favorite_genre="pop", favorite_mood="happy", target_energy=0.8, likes_acoustic=False
    )
    assert len(rec.recommend(user, k=1)) == 1
