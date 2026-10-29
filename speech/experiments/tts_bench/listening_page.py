"""Build one self-contained listening page per rater.

    python -m tts_bench.listening_page --raters azra nisa nisanur

Run it after ``tts_bench.listening``. It writes ``listening/dinle_<rater>.html``:
a single file with every clip embedded, so it works on Windows, macOS and
Linux in any browser (double-click), with nothing to install and no links to
break. Ratings are saved in the browser while rating, and the rater downloads
``rating_<rater>.csv`` at the end; put that file into ``listening/`` and run
``tts_bench.summarize``.

Each rater keeps the order of their rating sheet (``rating_<rater>.xlsx``) if
it exists, otherwise gets their own random order. Model names never appear in
the page: only the anonymous clip ids.

Audio is embedded as MP3 (128 kbps, mono) to keep the file small; every clip
goes through the same conversion, so the comparison stays fair. Use
``--format wav`` for lossless (about 4x bigger).
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import random
import shutil
import subprocess
from pathlib import Path

from .engines.base import EMOTIONS

TEMPLATE = Path(__file__).with_name("listening_page.html")
PLACEHOLDER = "/*__DATA__*/"


def encode_clip(path: Path, fmt: str = "mp3") -> tuple[str, bytes]:
    """(mime type, bytes) of one clip, converted with ffmpeg when asked for MP3."""
    if fmt == "mp3" and shutil.which("ffmpeg"):
        result = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-ac",
                "1",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "128k",
                "-f",
                "mp3",
                "-",
            ],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout:
            return "audio/mpeg", result.stdout
        print(f"ffmpeg could not convert {path.name}; embedding the WAV instead")
    return "audio/wav", path.read_bytes()


def _sheet_order(listening_dir: Path, rater: str) -> list[str]:
    sheet = listening_dir / f"rating_{rater}.xlsx"
    if not sheet.exists():
        return []
    from .listening import read_rating_sheet

    return [str(r["clip_id"]).strip() for r in read_rating_sheet(sheet) if r.get("clip_id")]


def clip_order(listening_dir: Path, rater: str, clip_ids: list[str], seed: int = 7) -> list[str]:
    """The rater's order from their sheet; their own random order otherwise."""
    wanted = set(clip_ids)
    order = [c for c in _sheet_order(listening_dir, rater) if c in wanted]
    if set(order) == wanted and len(order) == len(wanted):
        return order
    order = sorted(clip_ids)
    random.Random(f"{seed}:{rater}").shuffle(order)
    return order


def _page(rater: str, set_id: str, clips: list[dict[str, str]]) -> str:
    data = {"rater": rater, "set_id": set_id, "emotions": list(EMOTIONS), "clips": clips}
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace(PLACEHOLDER, payload)


def build_pages(listening_dir: Path, raters: list[str], fmt: str = "mp3", seed: int = 7) -> dict[str, Path]:
    key_path = listening_dir / "key.csv"
    if not key_path.exists():
        raise SystemExit(f"{key_path} not found. Run tts_bench.listening first.")
    with open(key_path, encoding="utf-8") as fh:
        clip_ids = [row["clip_id"] for row in csv.DictReader(fh)]
    clips_dir = listening_dir / "clips"
    missing = [c for c in clip_ids if not (clips_dir / f"{c}.wav").exists()]
    if missing:
        raise SystemExit(f"{len(missing)} clips missing in {clips_dir}, e.g. {missing[:3]}")

    print(f"Encoding {len(clip_ids)} clips as {fmt.upper()}...", flush=True)
    encoded: dict[str, dict[str, str]] = {}
    for cid in clip_ids:
        mime, data = encode_clip(clips_dir / f"{cid}.wav", fmt)
        encoded[cid] = {"id": cid, "mime": mime, "b64": base64.b64encode(data).decode("ascii")}

    set_id = hashlib.sha1(",".join(sorted(clip_ids)).encode()).hexdigest()[:10]
    pages: dict[str, Path] = {}
    for rater in raters:
        order = clip_order(listening_dir, rater, clip_ids, seed)
        path = listening_dir / f"dinle_{rater}.html"
        path.write_text(_page(rater, set_id, [encoded[c] for c in order]), encoding="utf-8")
        pages[rater] = path
    return pages


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--listening", default="listening", type=Path)
    parser.add_argument("--raters", nargs="+", default=["azra", "nisa", "nisanur"])
    parser.add_argument("--format", choices=["mp3", "wav"], default="mp3")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    pages = build_pages(args.listening, args.raters, args.format, args.seed)
    for rater, path in pages.items():
        print(f"{rater:<10} {path}  ({path.stat().st_size / 2**20:.1f} MB)")
    print("Send each person only their own dinle_<name>.html; they send back rating_<name>.csv.")


if __name__ == "__main__":
    main()
