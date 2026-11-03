"""Generate sample song intros with the real LLM and record how long each one took (#59).

Calls POST /api/dj/song-intro-preview on a running backend, one song after another,
like a broadcast: each request gets the song before it and the last 3 announcements.
Uses catalog songs from /api/tracks; fills up with made-up songs if the catalog is short.

Usage (backend running, from the backend folder with the venv active):
    python ../scripts/sample_song_intros.py
"""

import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000/api"
COUNT = 20
OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "samples" / "song-intros-raw.json"

# Made-up songs with different moods, used only when the catalog has too few songs.
EXTRA_SONGS = [
    {"title": "Morning Tide", "artist": "Lena Hart", "valence": 0.8, "arousal": 0.4},
    {"title": "Neon Run", "artist": "The Static Kids", "valence": 0.7, "arousal": 0.9},
    {"title": "Grey Window", "artist": "Owen Marsh", "valence": 0.2, "arousal": 0.2},
    {"title": "Paper Boats", "artist": "Mila Rae", "valence": 0.6, "arousal": 0.3},
    {"title": "Thunder Road Home", "artist": "Northbound", "valence": 0.5, "arousal": 0.8},
    {"title": "Slow Coffee", "artist": "June Avenue", "valence": 0.7, "arousal": 0.2},
    {"title": "Lost Signal", "artist": "Echo Field", "valence": 0.3, "arousal": 0.6},
    {"title": "Sunday Bikes", "artist": "The Fernwoods", "valence": 0.9, "arousal": 0.6},
    {"title": "Cold Harbor", "artist": "Ada Quinn", "valence": 0.1, "arousal": 0.4},
    {"title": "Fireflies", "artist": "Sol & Moon", "valence": 0.8, "arousal": 0.7},
    {"title": "Long Way Down", "artist": "Brass Hollow"},
    {"title": "City Lights", "artist": "Kai Rivers"},
    {"title": "Small Hours", "artist": "Nora Vale", "valence": 0.4, "arousal": 0.1},
    {"title": "Jump Start", "artist": "Volt Club", "valence": 0.9, "arousal": 0.95},
    {"title": "Old Photographs", "artist": "Henry Lake", "valence": 0.35, "arousal": 0.3},
    {"title": "Riverbend", "artist": "Clara Moss", "valence": 0.6, "arousal": 0.5},
    {"title": "Midnight Train", "artist": "The Lanterns", "valence": 0.4, "arousal": 0.7},
    {"title": "Golden Hour", "artist": "Iris Bloom", "valence": 0.85, "arousal": 0.5},
    {"title": "Static Rain", "artist": "Low Orbit", "valence": 0.25, "arousal": 0.5},
    {"title": "Weekend Plans", "artist": "Sunny Days Band", "valence": 0.95, "arousal": 0.8},
]


def load_songs(client: httpx.Client) -> list[dict]:
    try:
        # Short timeout: without Postgres this request would hang for a long time.
        tracks = client.get(f"{BASE_URL}/tracks", params={"limit": COUNT}, timeout=5).json()
    except (httpx.HTTPError, ValueError):
        tracks = []
    if not isinstance(tracks, list):  # e.g. an error message when Postgres is down
        tracks = []
    songs = [
        {
            "title": t["title"],
            "artist": t["artist"],
            "valence": t.get("valence"),
            "arousal": t.get("arousal"),
        }
        for t in tracks
    ]
    print(f"{len(songs)} songs from the catalog, {max(0, COUNT - len(songs))} made-up songs")
    return (songs + EXTRA_SONGS)[:COUNT]


def main() -> int:
    results = []
    with httpx.Client(timeout=120) as client:
        songs = load_songs(client)
        previous = None
        recent: list[str] = []
        for number, song in enumerate(songs, start=1):
            body = {"next_track": song, "previous_track": previous, "recent_announcements": recent}
            start = time.perf_counter()
            response = client.post(f"{BASE_URL}/dj/song-intro-preview", json=body)
            wall_ms = round((time.perf_counter() - start) * 1000)
            if response.status_code != 200:
                print(f"{number}: HTTP {response.status_code} {response.text}")
                return 1
            data = response.json()
            data.update(number=number, request=body, wall_ms=wall_ms)
            results.append(data)
            mark = "FALLBACK " if data["used_fallback"] else ""
            print(f"{number:2}. {data['llm_ms']:6} ms  {mark}[{data['emotion']}] {data['text']}")
            previous = {"title": song["title"], "artist": song["artist"]}
            recent = ([data["text"]] + recent)[:3]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
