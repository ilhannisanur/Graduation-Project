"""Check a running speech service end to end (standard library only).

Start the service first (see README), then in a second terminal:

    .venv/bin/python smoke_test.py               # http://127.0.0.1:8001
    .venv/bin/python smoke_test.py --play        # also open the audio in the default player
    .venv/bin/python smoke_test.py --url http://gpu-box:8001

It checks /health, synthesizes one sentence, downloads the audio, repeats the
same request (must come from the cache) and sends a bad request (must be 422).
Exit code 0 means everything passed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

SENTENCE = {"text": "Good evening, Ankara! It is a quiet night out there.", "emotion": "calm", "intensity": 0.6}


def call(method: str, url: str, body: dict | None = None, timeout: float = 600) -> tuple[int, bytes]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--play", action="store_true")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    failures = 0

    def check(ok: bool, label: str, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"[{'OK' if ok else 'FAIL'}] {label}  {detail}".rstrip())

    try:
        status, raw = call("GET", f"{base}/health", timeout=10)
    except urllib.error.URLError as err:
        print(f"[FAIL] service not reachable at {base}: {err.reason}. Is uvicorn running?")
        return 1
    health = json.loads(raw)
    primary = health.get("primary") or {}
    check(status == 200, "health", json.dumps(health))
    check(health.get("status") == "ok", "status is ok", f"(status={health.get('status')})")

    started = time.perf_counter()
    status, raw = call("POST", f"{base}/synthesize", SENTENCE)
    took = time.perf_counter() - started
    if status != 200:
        check(False, "synthesize", raw.decode(errors="replace")[:300])
        return 1
    first = json.loads(raw)
    check(True, "synthesize", f"engine={first['engine']} duration={first['duration_s']}s took={took:.1f}s")

    status, audio = call("GET", base + first["audio_url"])
    out = Path(tempfile.gettempdir()) / "speech_smoke_test.wav"
    out.write_bytes(audio)
    with wave.open(str(out)) as w:
        fmt = f"{w.getframerate()} Hz, {w.getnchannels()} channel(s), {w.getnframes() / w.getframerate():.2f}s"
        ok = status == 200 and w.getnchannels() == 1 and w.getframerate() == first["sample_rate"]
    check(ok, "audio file", f"{fmt} -> {out}")

    started = time.perf_counter()
    status, raw = call("POST", f"{base}/synthesize", SENTENCE)
    second = json.loads(raw)
    check(second.get("cached") is True, "same request served from cache", f"took={time.perf_counter() - started:.2f}s")

    status, raw = call("POST", f"{base}/synthesize", {"text": "hi", "emotion": "angry"})
    check(status == 422, "bad request rejected", f"(HTTP {status})")

    verdict = "ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED"
    print(f"\n{verdict} (main engine: {primary.get('engine')})")
    if args.play:
        opener = "xdg-open" if sys.platform.startswith("linux") else "open"
        if sys.platform.startswith("win"):
            import os

            os.startfile(out)  # type: ignore[attr-defined]
        else:
            subprocess.Popen([opener, str(out)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
