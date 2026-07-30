"""
Command line runner for the Music Recommender Simulation.

This file helps you quickly run and test your recommender.

You will implement the functions in recommender.py:
- load_songs
- score_song
- recommend_songs
"""

from src.recommender import load_songs, recommend_songs

def main() -> None:
    songs = load_songs("data/songs.csv") 
    #print(songs)

    # Starter example profile
    user_prefs = {"genre": "pop", "mood": "happy", "energy": 0.8}
    user_prefs_1 = {
        "genre": "Chill lofi",
        "mood": "chill",
        "energy" : 0.40
    }
    user_prefs_2 = {
        "genre": "High-energy pop",
        "mood": "happy",
        "energy": 0.85
    }
    user_prefs_3 = {
        "genre": "Deep Intense Rock",
        "mood": "intense",
        "energy": 0.95
    }

    recommendations = recommend_songs(user_prefs_3, songs, k=5)

    print("\nTop recommendations:\n")
    for rec in recommendations:
        # You decide the structure of each returned item.
        # A common pattern is: (song, score, explanation)
        song, score, explanation = rec
        print(f"{song['title']} - Score: {score:.2f}")
        print(f"Because: {explanation}")
        print()


if __name__ == "__main__":
    main()
