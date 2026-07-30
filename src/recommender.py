import csv
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

@dataclass
class Song:
    """
    Represents a song and its attributes.
    Required by tests/test_recommender.py
    """
    id: int
    title: str
    artist: str
    genre: str
    mood: str
    energy: float
    tempo_bpm: float
    valence: float
    danceability: float
    acousticness: float

@dataclass
class UserProfile:
    """
    Represents a user's taste preferences.
    Required by tests/test_recommender.py

    ``target_valence`` was added so the profile can express every signal the
    scorer understands. It defaults to ``None`` so existing callers (and the
    starter tests) keep working without passing it.
    """
    favorite_genre: str
    favorite_mood: str
    target_energy: float
    likes_acoustic: bool
    target_valence: Optional[float] = None

    def to_prefs(self) -> Dict:
        """
        Convert this profile into the dict shape ``score_song`` expects.

        Keeping a single scoring implementation (``score_song``) means the
        OOP ``Recommender`` and the functional API can never drift apart.
        Keys are only included when they carry a real preference, so an unset
        field simply doesn't contribute to (or subtract from) the score.
        """
        prefs: Dict = {
            "genre": self.favorite_genre,
            "mood": self.favorite_mood,
            "energy": self.target_energy,
            "likes_acoustic": self.likes_acoustic,
        }
        if self.target_valence is not None:
            prefs["valence"] = self.target_valence
        return prefs

class Recommender:
    """
    OOP implementation of the recommendation logic.
    Required by tests/test_recommender.py

    Rather than duplicate the scoring rules, this class delegates to the same
    ``score_song`` function the functional API uses, so both paths always agree.
    """
    def __init__(self, songs: List[Song]):
        self.songs = songs

    def _score(self, user: UserProfile, song: Song) -> Tuple[float, List[str]]:
        return score_song(user.to_prefs(), asdict(song))

    def recommend(self, user: UserProfile, k: int = 5) -> List[Song]:
        """Return the top ``k`` songs, highest score first (stable on ties)."""
        scored = [(song, self._score(user, song)[0]) for song in self.songs]
        scored.sort(key=lambda entry: entry[1], reverse=True)
        return [song for song, _score in scored[:k]]

    def explain_recommendation(self, user: UserProfile, song: Song) -> str:
        """Return a human-readable reason string for why ``song`` fits ``user``."""
        _total, reasons = self._score(user, song)
        return "; ".join(reasons) if reasons else "No matching preferences"

def load_songs(csv_path: str) -> List[Dict]:
    """
    Loads songs from a CSV file.
    Required by src/main.py
    """
    int_fields = {"id", "tempo_bpm"}
    float_fields = {"energy", "valence", "danceability", "acousticness"}

    songs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for field in int_fields:
                row[field] = int(row[field])
            for field in float_fields:
                row[field] = float(row[field])
            songs.append(row)
    return songs

def score_song(user_prefs: Dict, song: Dict) -> Tuple[float, List[str]]:
    """Scores a song against user_prefs using the weighted algorithm recipe, returning (score, reasons)."""
    score = 0.0
    reasons: List[str] = []

    # Mood match - 3 pts
    favorite_mood = user_prefs.get("mood")
    if favorite_mood is not None and song["mood"] == favorite_mood:
        score += 3
        reasons.append(f"mood matched ({song['mood']})")

    # Genre match - 2 pts
    favorite_genre = user_prefs.get("genre")
    if favorite_genre is not None and song["genre"] == favorite_genre:
        score += 2
        reasons.append(f"genre matched ({song['genre']})")

    # Energy closeness - 2 pts
    target_energy = user_prefs.get("energy")
    if target_energy is not None:
        energy_score = 2 * (1 - abs(song["energy"] - target_energy))
        score += energy_score
        reasons.append(f"energy close: {song['energy']:.2f} vs target {target_energy:.2f}")

    # Valence closeness - 2 pts
    target_valence = user_prefs.get("valence")
    if target_valence is not None:
        valence_score = 2 * (1 - abs(song["valence"] - target_valence))
        score += valence_score
        reasons.append(f"valence close: {song['valence']:.2f} vs target {target_valence:.2f}")

    # Acousticness alignment - 1 pt
    likes_acoustic = user_prefs.get("likes_acoustic")
    if likes_acoustic is not None:
        acoustic_score = song["acousticness"] if likes_acoustic else (1 - song["acousticness"])
        score += acoustic_score
        reasons.append(f"acousticness aligned ({song['acousticness']:.2f})")

    return score, reasons

def recommend_songs(user_prefs: Dict, songs: List[Dict], k: int = 5) -> List[Tuple[Dict, float, str]]:
    """Scores every song with score_song and returns the top k, sorted highest score first."""
    scored = [(song, *score_song(user_prefs, song)) for song in songs]
    scored.sort(key=lambda entry: entry[1], reverse=True)

    return [
        (song, score, "; ".join(reasons) if reasons else "No matching preferences")
        for song, score, reasons in scored[:k]
    ]
