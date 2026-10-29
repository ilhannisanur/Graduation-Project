"""Try one sentence with one engine - the quickest way to hear a model.

    python -m tts_bench.say --engine kokoro --emotion happy "Good morning, Ankara!"
    python -m tts_bench.say --engine chatterbox --emotion sad --intensity 0.9 --play "Some difficult news tonight."
    python -m tts_bench.say --engine chatterbox --refs refs --emotion excited --out try.wav "What a finish!"

Writes the audio to a wav file (default: say_<engine>_<emotion>.wav) and prints the settings used.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .engines import available_engines, create_engine
from .engines.base import EMOTIONS, SynthesisRequest
from .run import _parse_options, _write_wav


def _is_wsl() -> bool:
    return "microsoft" in platform.release().lower()


def _play(path: Path) -> None:
    """Open the file in the default player (Windows, WSL, Linux desktop, macOS)."""
    path = path.resolve()
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif _is_wsl() and shutil.which("explorer.exe"):
            # WSL on Windows 10 has no Linux audio: let Windows play it
            win_path = subprocess.run(["wslpath", "-w", str(path)], capture_output=True, text=True).stdout.strip()
            subprocess.run(["explorer.exe", win_path], check=False)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif shutil.which("xdg-open"):
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("aplay"):
            subprocess.run(["aplay", "-q", str(path)], check=False)
        else:
            print(f"Open {path} in an audio player.")
    except OSError as exc:
        print(f"Could not open a player ({exc}). Open {path} manually.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("text", help="English sentence to speak")
    parser.add_argument("--engine", required=True, choices=available_engines())
    parser.add_argument("--emotion", default="neutral", choices=EMOTIONS)
    parser.add_argument("--intensity", type=float, default=0.7)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--refs", type=Path, help="folder with <emotion>.wav reference clips")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--play", action="store_true", help="open the result in the default player")
    parser.add_argument("--option", action="append", default=[], metavar="KEY=VALUE")
    args = parser.parse_args(argv)

    engine = create_engine(args.engine, device=args.device, refs_dir=args.refs, **_parse_options(args.option))
    req = SynthesisRequest(text=args.text, emotion=args.emotion, intensity=args.intensity)

    print(f"Loading {args.engine} on {args.device} (the first run downloads the model)...", flush=True)
    t0 = time.perf_counter()
    engine.load()
    print(f"Loaded in {time.perf_counter() - t0:.1f} s. Settings: {json.dumps(engine.settings_for(req))}")

    t0 = time.perf_counter()
    audio = engine.synthesize(req)
    synth = time.perf_counter() - t0
    out = args.out or Path(f"say_{args.engine}_{args.emotion}.wav")
    _write_wav(out, audio.samples, audio.sample_rate)
    print(f"Wrote {out}: {audio.duration_sec:.1f} s of audio in {synth:.1f} s (RTF {synth / audio.duration_sec:.2f})")
    if args.play:
        _play(out)


if __name__ == "__main__":
    main()
