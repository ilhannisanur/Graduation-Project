"""Generate the test set with one engine and record timing/quality metrics.

    python -m tts_bench.run --engine kokoro
    python -m tts_bench.run --engine chatterbox --refs refs --label chatterbox-cpu
    python -m tts_bench.run --engine chatterbox --device cuda --label chatterbox-t4

Output: results/<label>/<item_id>.wav, metrics.csv and run_info.json
An interrupted run continues with --resume.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from . import audio_stats
from .engines import available_engines, create_engine
from .engines.base import SynthesisRequest, TTSEngine
from .test_set import DEFAULT_TEST_SET, BenchItem, load_test_set

METRIC_FIELDS = [
    "label",
    "engine",
    "device",
    "item_id",
    "group",
    "listen",
    "emotion",
    "intensity",
    "text_chars",
    "audio_sec",
    "synth_sec",
    "rtf",
    "sample_rate",
    "peak_dbfs",
    "rms_dbfs",
    "lufs",
    "lead_silence_sec",
    "tail_silence_sec",
    "settings",
]


def _peak_memory_mb() -> dict[str, float | None]:
    result: dict[str, float | None] = {"ram_peak_mb": None, "gpu_peak_mb": None}
    try:
        import psutil

        info = psutil.Process().memory_info()
        # peak_wset exists on Windows; elsewhere fall back to current RSS
        result["ram_peak_mb"] = round(getattr(info, "peak_wset", info.rss) / 2**20, 1)
    except ImportError:
        pass
    torch = sys.modules.get("torch")
    if torch is not None and torch.cuda.is_available():
        result["gpu_peak_mb"] = round(torch.cuda.max_memory_allocated() / 2**20, 1)
    return result


def _write_wav(path: Path, samples: np.ndarray, sample_rate: int) -> None:
    sf.write(str(path), np.clip(samples, -1.0, 1.0), sample_rate, subtype="PCM_16")


def _read_existing(metrics_path: Path) -> list[dict[str, Any]]:
    if not metrics_path.exists():
        return []
    with open(metrics_path, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # an older metrics.csv with different columns cannot be resumed
    return rows if rows and set(METRIC_FIELDS) <= set(rows[0]) else []


def run_benchmark(
    engine: TTSEngine,
    items: list[BenchItem],
    out_dir: Path,
    label: str,
    warmup: bool = True,
    resume: bool = False,
) -> list[dict[str, Any]]:
    """Generate every item, writing metrics.csv row by row.

    With ``resume`` the items already in metrics.csv (and on disk) are skipped,
    so a long CPU run that was interrupted continues where it stopped.
    A failing item is reported and skipped instead of aborting the run.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = out_dir / "metrics.csv"

    rows: list[dict[str, Any]] = []
    if resume:
        rows = [r for r in _read_existing(metrics_path) if (out_dir / f"{r['item_id']}.wav").exists()]
    done = {r["item_id"] for r in rows}
    todo = [it for it in items if it.id not in done]
    if done:
        print(f"Resuming: {len(done)} done, {len(todo)} to go", flush=True)

    with open(metrics_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    load_sec = warmup_sec = None
    errors: list[dict[str, str]] = []
    if todo:
        t0 = time.perf_counter()
        engine.load()
        load_sec = round(time.perf_counter() - t0, 3)

        if warmup:  # the first call is always slower (lazy init, caches)
            t0 = time.perf_counter()
            engine.synthesize(SynthesisRequest(text="Warming up the studio.", emotion="neutral"))
            warmup_sec = round(time.perf_counter() - t0, 3)

    for i, item in enumerate(todo, 1):
        req = item.request
        try:
            t0 = time.perf_counter()
            audio = engine.synthesize(req)
            synth_sec = time.perf_counter() - t0
            if audio.duration_sec <= 0:
                raise RuntimeError("empty audio")
        except Exception as exc:  # keep going: one bad sentence should not cost a 40-minute run
            errors.append({"item_id": item.id, "error": f"{type(exc).__name__}: {exc}"[:500]})
            print(f"[{i}/{len(todo)}] {item.id:<18} FAILED: {exc}", flush=True)
            continue

        _write_wav(out_dir / f"{item.id}.wav", audio.samples, audio.sample_rate)
        lead, tail = audio_stats.edge_silence_sec(audio.samples, audio.sample_rate)
        row = {
            "label": label,
            "engine": engine.name,
            "device": engine.device,
            "item_id": item.id,
            "group": item.group,
            "listen": int(item.listen),
            "emotion": req.emotion,
            "intensity": req.intensity,
            "text_chars": len(req.text),
            "audio_sec": round(audio.duration_sec, 3),
            "synth_sec": round(synth_sec, 3),
            "rtf": round(synth_sec / audio.duration_sec, 3),
            "sample_rate": audio.sample_rate,
            "peak_dbfs": audio_stats.peak_dbfs(audio.samples),
            "rms_dbfs": audio_stats.rms_dbfs(audio.samples),
            "lufs": audio_stats.loudness_lufs(audio.samples, audio.sample_rate),
            "lead_silence_sec": lead,
            "tail_silence_sec": tail,
            "settings": json.dumps(engine.settings_for(req), ensure_ascii=False),
        }
        rows.append(row)
        with open(metrics_path, "a", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=METRIC_FIELDS).writerow(row)
        print(
            f"[{i}/{len(todo)}] {item.id:<18} audio={row['audio_sec']:>6}s "
            f"synth={row['synth_sec']:>7}s rtf={row['rtf']}",
            flush=True,
        )

    info_path = out_dir / "run_info.json"
    previous = json.loads(info_path.read_text(encoding="utf-8")) if resume and info_path.exists() else {}
    info = {
        "label": label,
        **engine.info(),
        "refs_dir": str(engine.refs_dir) if engine.refs_dir else None,
        "seed": engine.seed,
        "load_sec": load_sec if load_sec is not None else previous.get("load_sec"),
        "warmup_sec": warmup_sec if warmup_sec is not None else previous.get("warmup_sec"),
        **_peak_memory_mb(),
        "items": len(rows),
        "items_planned": len(items),
        "errors": errors,
        "emotions": sorted({r["emotion"] for r in rows}),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count(),
        "torch": getattr(sys.modules.get("torch"), "__version__", None),
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if previous and info["ram_peak_mb"] is not None and previous.get("ram_peak_mb"):
        info["ram_peak_mb"] = max(info["ram_peak_mb"], previous["ram_peak_mb"])
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return rows


def _parse_options(pairs: list[str]) -> dict[str, str]:
    options = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--option expects key=value, got {pair!r}")
        key, value = pair.split("=", 1)
        options[key.strip()] = value.strip()
    return options


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", required=True, choices=available_engines())
    parser.add_argument("--device", default="cpu", help="cpu or cuda")
    parser.add_argument("--label", help="results folder name (default: <engine>-<device>)")
    parser.add_argument("--out", default="results", type=Path)
    parser.add_argument("--refs", type=Path, help="folder with <emotion>.wav reference clips")
    parser.add_argument("--test-set", default=DEFAULT_TEST_SET, type=Path)
    parser.add_argument(
        "--only",
        choices=["shared", "content", "listen"],
        help="run a subset: the shared sentence, the content sentences, or the 14 listening-test items",
    )
    parser.add_argument("--limit", type=int, help="first N items (quick check)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-warmup", action="store_true")
    parser.add_argument("--resume", action="store_true", help="skip items already generated in this folder")
    parser.add_argument(
        "--option",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="engine option, e.g. voice=af_bella or tags=true (repeatable)",
    )
    args = parser.parse_args(argv)

    if args.refs and not args.refs.is_dir():
        raise SystemExit(f"refs folder not found: {args.refs}")

    items = load_test_set(args.test_set)
    if args.only == "listen":
        items = [it for it in items if it.listen]
    elif args.only:
        items = [it for it in items if it.group == args.only]
    if args.limit:
        items = items[: args.limit]

    label = args.label or f"{args.engine}-{args.device}"
    engine = create_engine(
        args.engine, device=args.device, refs_dir=args.refs, seed=args.seed, **_parse_options(args.option)
    )
    rows = run_benchmark(engine, items, args.out / label, label, warmup=not args.no_warmup, resume=args.resume)

    rtfs = [float(r["rtf"]) for r in rows if r.get("rtf") not in (None, "")]
    mean_rtf = f"{np.mean(rtfs):.2f}" if rtfs else "-"
    print(f"\nDone: {len(rows)}/{len(items)} clips in {args.out / label}  mean RTF = {mean_rtf}")
    if len(rows) < len(items):
        print("Some items failed (see run_info.json). Fix the cause and rerun with --resume.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
