"""Listen to the radio from the terminal: checks the whole chain without the web player.

Start Postgres, the speech service and the backend first (README), then in backend/:

    python -m app.radio.check                  # song -> announcement -> song
    python -m app.radio.check --save ../data/check
    python -m app.radio.check --url http://192.168.1.20:8000

It does what the player does: opens a session, asks for the next segment three
times and downloads every audio file. Between the songs it waits a little (as if the
song were playing), so the announcement has time to be written and voiced.
Exit code 0 means the radio works end to end.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

ORDER = ["track", "announcement", "track"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default="http://localhost:8000", help="backend address")
    parser.add_argument(
        "--listen",
        type=float,
        default=30.0,
        help="seconds to wait after a song, like a listener (default 30)",
    )
    parser.add_argument("--save", type=Path, help="folder to save the downloaded audio in")
    args = parser.parse_args(argv)

    failures = 0

    def check(ok: bool, label: str, detail: str = "") -> bool:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"[{'OK' if ok else 'FAIL'}] {label}  {detail}".rstrip())
        return ok

    with httpx.Client(base_url=args.url.rstrip("/"), timeout=120) as http:
        try:
            health = http.get("/api/health").json()
        except httpx.HTTPError as exc:
            print(f"[FAIL] backend not reachable at {args.url}: {exc}. Is uvicorn running?")
            return 1
        check(health.get("db") == "up", "backend and database", str(health))

        speech = http.get("/api/speech/health")
        engine = (speech.json().get("primary") or {}).get("engine")
        check(
            speech.status_code == 200,
            "speech service",
            f"status={speech.json().get('status')} engine={engine}",
        )

        created = http.post("/api/sessions")
        ok = created.status_code == 201
        if not check(ok, "session", "" if ok else created.text[:300]):
            return 1
        session_id = created.json()["session_id"]

        kinds = []
        try:
            for number in range(1, len(ORDER) + 1):
                response = http.get(f"/api/sessions/{session_id}/next")
                ok = response.status_code == 200
                if not check(ok, f"segment {number}", "" if ok else response.text[:300]):
                    break
                body = response.json()
                segment = body["segment"]
                kinds.append(segment["kind"])
                if segment["kind"] == "track":
                    what = f"song: {segment['title']} - {segment['artist']}"
                else:
                    what = f"announcement ({segment['emotion']}): {segment['text']}"
                if body.get("announcement_skipped"):
                    what += f"  [announcement skipped: {body['announcement_skipped']}]"
                print(f"     {number}. {what}")

                audio = http.get(segment["audio_url"])
                content_type = audio.headers.get("content-type", "")
                check(
                    audio.status_code == 200 and content_type.startswith("audio/"),
                    f"segment {number} audio",
                    f"{segment['audio_url']} -> {audio.status_code} {content_type}, "
                    f"{len(audio.content) / 1024:.0f} KB",
                )
                if args.save and audio.status_code == 200:
                    args.save.mkdir(parents=True, exist_ok=True)
                    suffix = ".wav" if "wav" in content_type else ".mp3"
                    path = args.save / f"{number}-{segment['kind']}{suffix}"
                    path.write_bytes(audio.content)
                    print(f"     saved {path}")

                if segment["kind"] == "track" and number < len(ORDER):
                    print(f"     listening for {args.listen:g} s ...")
                    time.sleep(args.listen)
        finally:
            try:
                http.delete(f"/api/sessions/{session_id}")
            except httpx.HTTPError:
                pass  # the session expires by itself

    check(kinds == ORDER, "order song -> announcement -> song", " -> ".join(kinds))
    if kinds and kinds != ORDER:
        print(
            "     No announcement: check the speech service (/api/speech/health) and the "
            "backend log. A slow first run (model download) may need --listen 120."
        )
    print("\nRADIO WORKS END TO END" if failures == 0 else f"\n{failures} CHECK(S) FAILED")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
