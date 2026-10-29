"""ElevenLabs helpers: check the key and quota, and choose a voice.

    python -m tts_bench.elevenlabs_tools check                    # key, plan, quota, voice, cost of the test set
    python -m tts_bench.elevenlabs_tools voices --gender female   # premade voices to choose from

Put the chosen voice into .env:  ELEVENLABS_VOICE_ID=<voice_id>
The other engines speak with a female voice by default (Kokoro af_heart,
Chatterbox built-in, StyleTTS2 LJSpeech, Orpheus tara), so a female voice
keeps the blind listening test fair.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from .engines.elevenlabs_engine import API_BASE, ElevenLabsEngine, ElevenLabsError, load_api_key
from .test_set import load_test_set

WARMUP_TEXT = "Warming up the studio."


def _get_json(path: str, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(API_BASE + path, headers={"xi-api-key": api_key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise ElevenLabsError(err.code, err.read().decode("utf-8", "replace")[:300]) from None


def count_test_set_characters(engine: ElevenLabsEngine | None = None) -> int:
    """Characters one full run sends (test set with emotion tags + warm-up sentence)."""
    engine = engine or ElevenLabsEngine()
    texts = [engine.settings_for(item.request)["text"] for item in load_test_set()]
    return sum(len(t) for t in texts) + len(WARMUP_TEXT)


def list_voices(api_key: str) -> list[dict[str, Any]]:
    try:
        data = _get_json("/v2/voices?page_size=100&voice_type=default", api_key)
    except ElevenLabsError as err:
        if err.status not in (404, 405, 422):
            raise
        data = _get_json("/v1/voices", api_key)  # older endpoint
    return list(data.get("voices", []))


def format_voices(voices: list[dict[str, Any]], gender: str | None = None) -> str:
    rows = []
    for v in voices:
        labels = v.get("labels") or {}
        if gender and str(labels.get("gender", "")).lower() != gender.lower():
            continue
        rows.append(
            (
                str(v.get("name", "")),
                str(labels.get("gender", "")),
                str(labels.get("age", "")),
                str(labels.get("accent", "")),
                str(labels.get("use_case") or labels.get("use case") or ""),
                str(v.get("voice_id", "")),
            )
        )
    rows.sort()
    header = ("name", "gender", "age", "accent", "use case", "voice_id")
    widths = [max(len(r[i]) for r in [header, *rows]) for i in range(len(header))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)) for row in [header, *rows]]
    return "\n".join(lines) + f"\n\n{len(rows)} voices"


def check(api_key: str) -> int:
    engine = ElevenLabsEngine()
    needed = count_test_set_characters(engine)
    print(f"key        : {api_key[:4]}...{api_key[-2:]}")
    print(f"model      : {engine.model_id}")
    status = 0
    try:
        voice = _get_json(f"/v1/voices/{urllib.parse.quote(engine.voice_id)}", api_key)
        labels = voice.get("labels") or {}
        who = f"{voice.get('name')} ({labels.get('gender', '?')}, {labels.get('accent', '?')})"
        print(f"voice      : {who} {engine.voice_id}")
    except ElevenLabsError as err:
        print(f"voice      : {engine.voice_id} -> NOT USABLE (HTTP {err.status})")
        status = 1
    try:
        sub = _get_json("/v1/user/subscription", api_key)
        used, limit = int(sub.get("character_count", 0)), int(sub.get("character_limit", 0))
        reset = sub.get("next_character_count_reset_unix")
        reset_text = datetime.fromtimestamp(reset, tz=timezone.utc).strftime("%Y-%m-%d") if reset else "?"
        print(f"plan       : {sub.get('tier', '?')}")
        print(f"quota      : {used:,} / {limit:,} used, {limit - used:,} left (resets {reset_text})")
        print(f"test set   : about {needed:,} characters per full run")
        if limit - used < needed:
            print("WARNING    : not enough characters left for a full run")
            status = 1
    except ElevenLabsError as err:
        print(f"quota      : not readable (HTTP {err.status}); give the key the 'User: read' permission to see it")
        print(f"test set   : about {needed:,} characters per full run")
    return status


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="key, plan, quota and the voice in use")
    voices = sub.add_parser("voices", help="list premade voices")
    voices.add_argument("--gender", help="female / male")
    args = parser.parse_args(argv)

    api_key = load_api_key()
    if not api_key:
        raise SystemExit("ELEVENLABS_API_KEY not found. Put it in speech/experiments/.env")
    if args.command == "voices":
        print(format_voices(list_voices(api_key), args.gender))
        print("Set one in .env:  ELEVENLABS_VOICE_ID=<voice_id>")
        return
    raise SystemExit(check(api_key))


if __name__ == "__main__":
    main()
