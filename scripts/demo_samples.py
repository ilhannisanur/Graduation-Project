"""Make the "Seven feelings" voice samples for the studio screen.

One short DJ line per emotion, voiced by the running speech service (Orpheus on the GPU),
saved to data/demo/emotions/ with a manifest.json the backend serves
(GET /api/station/emotions). Audio files stay out of git (data/ is ignored).

Intensity is kept at 0.4: at 0.5 and above Orpheus adds tags such as <laugh> or <gasp>,
which made squeaky sounds in our tests; without them the wording carries the emotion.

Usage (speech service running on port 8001, from the backend folder with the venv active):
    python ../scripts/demo_samples.py
"""

import json
import sys
from pathlib import Path

import httpx

SPEECH_URL = "http://127.0.0.1:8001"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "demo" / "emotions"
INTENSITY = 0.4

LINES = [
    ("neutral", "Neutral", "It is twenty to three in Ankara, and this is your AI radio."),
    (
        "happy",
        "Happy",
        "Great news today: the city park finally opens again, and it is sunny all week!",
    ),
    (
        "excited",
        "Excited",
        "Oh, this is it! Turn it up, the next song is one of my all-time favourites!",
    ),
    (
        "calm",
        "Calm",
        "Take a slow breath. The rain is soft outside, so here is something gentle.",
    ),
    (
        "sad",
        "Sad",
        "Some sad news tonight. An old friend of this station has passed away. We miss you.",
    ),
    (
        "serious",
        "Serious",
        "A storm warning is in effect for the region. Please stay indoors until evening.",
    ),
    (
        "surprised",
        "Surprised",
        "Wait, what? Snow in May? Nobody saw that coming, not even the forecast!",
    ),
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    with httpx.Client(base_url=SPEECH_URL, timeout=300) as client:
        try:
            client.get("/health").raise_for_status()
        except httpx.HTTPError as exc:
            print(f"Speech service not reachable at {SPEECH_URL}: {exc}")
            return 1
        for emotion, label, text in LINES:
            print(f"{label:<10} voicing…", flush=True)
            answer = client.post(
                "/synthesize", json={"text": text, "emotion": emotion, "intensity": INTENSITY}
            )
            answer.raise_for_status()
            info = answer.json()
            audio = client.get(info["audio_url"])
            audio.raise_for_status()
            name = f"{emotion}.wav"
            (OUT_DIR / name).write_bytes(audio.content)
            manifest.append({"emotion": emotion, "label": label, "text": text, "file": name})
            print(f"{label:<10} {info['duration_s']:.1f} s with {info['engine']}")
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Saved {len(manifest)} samples to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
