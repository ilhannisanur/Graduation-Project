"""Combine metrics, automatic emotion scores and blind listening ratings into
the Markdown tables of docs/tts-karsilastirma.md.

    python -m tts_bench.summarize            # writes results/summary.md

Tables:
  1. speed and resources per model
  2. blind listening scores of every rater, per model (issue #4 acceptance criterion)
  3. which emotions listeners recognised, per model
  4. how each model expressed each emotion (parameters and tags actually used)
  5. listener notes per model (pronunciation, glitches)
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean

from .engines.base import EMOTIONS
from .listening import read_rating_sheet

ANNOUNCEMENT_SEC = 15.0  # typical DJ announcement length
SONG_SEC = 180.0  # the next announcement can be generated while a song plays


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _avg(values: list[float], digits: int = 2) -> float | None:
    return round(mean(values), digits) if values else None


def _pct(values: list[int]) -> str:
    return f"{100 * mean(values):.0f}%" if values else "-"


def _fmt(value) -> str:
    return "-" if value is None else str(value)


def _row(cells: list) -> str:
    return "| " + " | ".join(_fmt(c) for c in cells) + " |"


def _header(cells: list[str]) -> list[str]:
    return [_row(cells), "|" + "---|" * len(cells)]


def _filled(rows: list[dict[str, str]]) -> int:
    return sum(1 for r in rows if str(r.get("perceived_emotion") or "").strip())


def _rating_sheets(listening_dir: Path) -> dict[str, tuple[Path, list[dict[str, str]]]]:
    """rater -> (file, rows). Of rating_<rater>.xlsx / .csv (also "rating_nisa (1).csv"
    from a second browser download) the most completely filled one wins; on a tie the newest."""
    best: dict[str, tuple[int, float, Path, list[dict[str, str]]]] = {}
    for path in sorted(listening_dir.glob("rating_*.*")):
        if path.suffix.lower() not in (".xlsx", ".csv") or path.name.startswith(("~$", ".~lock")):
            continue
        rater = re.sub(r"\s*\(\d+\)$", "", path.stem.removeprefix("rating_")).strip()
        rows = read_rating_sheet(path)
        rank = (_filled(rows), path.stat().st_mtime)
        if rater not in best or rank > best[rater][:2]:
            best[rater] = (*rank, path, rows)
    return {rater: (v[2], v[3]) for rater, v in sorted(best.items())}


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "x", "evet"}


def collect_ratings(listening_dir: Path | None) -> tuple[list[str], list[dict[str, str]]]:
    """Returns (raters, one record per rated clip with model, emotion, group, scores)."""
    if not listening_dir or not (listening_dir / "key.csv").exists():
        return [], []
    key = {r["clip_id"]: r for r in _read_csv(listening_dir / "key.csv")}
    raters: list[str] = []
    records: list[dict[str, str]] = []
    for rater, (_sheet, rows) in _rating_sheets(listening_dir).items():
        raters.append(rater)
        for row in rows:
            meta = key.get(str(row.get("clip_id", "")).strip())
            if meta is None:
                continue
            records.append(
                {
                    "rater": rater,
                    "label": meta["label"],
                    "emotion": meta["emotion"],
                    "group": meta["group"],
                    "naturalness": str(row.get("naturalness", "")).strip(),
                    "perceived": str(row.get("perceived_emotion", "")).strip().lower(),
                    # pronunciation_issue comes from the listening page; pronunciation_notes from a hand-made column
                    "pron": int(
                        _truthy(row.get("pronunciation_issue"))
                        or bool(str(row.get("pronunciation_notes") or "").strip())
                    ),
                    "notes": " / ".join(
                        t
                        for t in (
                            str(row.get("notes") or "").strip(),
                            str(row.get("pronunciation_notes") or "").strip(),
                        )
                        if t
                    ),
                }
            )
    return raters, records


def _technical_table(results_dir: Path) -> list[str]:
    lines = _header(
        [
            "Model (setup)",
            "Clips",
            "Load (s)",
            "Mean RTF",
            "15 s announcement takes (s)",
            "Fits in a song?",
            "RAM / GPU peak (MB)",
            "Silence start / end (s)",
            "Auto emotion match",
        ]
    )
    for run_dir in sorted(p for p in results_dir.iterdir() if (p / "metrics.csv").exists()):
        metrics = _read_csv(run_dir / "metrics.csv")
        info_path = run_dir / "run_info.json"
        info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
        rtf = _avg([float(r["rtf"]) for r in metrics if r.get("rtf")])
        gen_sec = round(rtf * ANNOUNCEMENT_SEC, 1) if rtf is not None else None
        fits = None if gen_sec is None else ("yes" if gen_sec < SONG_SEC else "no")
        lead = _avg([float(r["lead_silence_sec"]) for r in metrics if r.get("lead_silence_sec")])
        tail = _avg([float(r["tail_silence_sec"]) for r in metrics if r.get("tail_silence_sec")])
        scores = [r for r in _read_csv(run_dir / "emotion_scores.csv") if r.get("match") not in ("", None)]
        lines.append(
            _row(
                [
                    run_dir.name,
                    f"{len(metrics)}/{info.get('items_planned', len(metrics))}",
                    info.get("load_sec"),
                    rtf,
                    gen_sec,
                    fits,
                    f"{_fmt(info.get('ram_peak_mb'))} / {_fmt(info.get('gpu_peak_mb'))}",
                    f"{_fmt(lead)} / {_fmt(tail)}",
                    _pct([int(r["match"]) for r in scores]),
                ]
            )
        )
    return lines


def _listening_table(raters: list[str], records: list[dict[str, str]]) -> list[str]:
    cols = ["Model"]
    cols += [f"Naturalness: {r}" for r in raters] + ["Naturalness: mean"]
    cols += [f"Emotion hit: {r}" for r in raters] + ["Emotion hit: mean", "Hit on shared sentence"]
    cols += ["Pronunciation/glitch flagged"]
    lines = _header(cols)
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rec in records:
        by_label[rec["label"]].append(rec)
    for label in sorted(by_label):
        recs = by_label[label]
        nat = {r: [float(x["naturalness"]) for x in recs if x["rater"] == r and x["naturalness"]] for r in raters}
        hit = {
            r: [int(x["perceived"] == x["emotion"]) for x in recs if x["rater"] == r and x["perceived"]] for r in raters
        }
        shared = [int(x["perceived"] == x["emotion"]) for x in recs if x["group"] == "shared" and x["perceived"]]
        cells: list = [label]
        cells += [_avg(nat[r]) for r in raters] + [_avg([v for r in raters for v in nat[r]])]
        cells += [_pct(hit[r]) for r in raters] + [_pct([v for r in raters for v in hit[r]]), _pct(shared)]
        cells += [_pct([x["pron"] for x in recs if x["perceived"] or x["naturalness"]])]
        lines.append(_row(cells))
    return lines


def _notes_list(records: list[dict[str, str]]) -> list[str]:
    lines: list[str] = []
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for rec in records:
        if rec.get("notes"):
            by_label[rec["label"]].append(rec)
    for label in sorted(by_label):
        lines.append(f"**{label}**")
        lines += [f"- {r['rater']}, {r['emotion']}: {r['notes']}" for r in by_label[label]]
        lines.append("")
    return lines or ["_No notes._", ""]


def _emotion_table(records: list[dict[str, str]]) -> list[str]:
    lines = _header(["Model", *EMOTIONS])
    hits: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for rec in records:
        if rec["perceived"]:
            hits[rec["label"]][rec["emotion"]].append(int(rec["perceived"] == rec["emotion"]))
    for label in sorted(hits):
        lines.append(_row([label, *(_pct(hits[label][e]) for e in EMOTIONS)]))
    return lines


# keys that do not describe the emotion (identity or the text itself)
_NOT_EMOTION_KEYS = {"text", "prompt", "voice", "voice_id", "model", "reference"}


def _controls(settings_json: str) -> str:
    """'exaggeration=0.8, cfg_weight=0.45' from the settings stored in metrics.csv."""
    try:
        settings = json.loads(settings_json)
    except (TypeError, ValueError):
        return "-"
    parts = []
    for key, value in settings.items():
        if key in _NOT_EMOTION_KEYS:
            continue
        if isinstance(value, dict):
            parts += [f"{k}={v}" for k, v in value.items()]
        elif value not in ("", None):
            parts.append(f"{key}={value}")
    text = settings.get("text") or settings.get("prompt") or ""
    if text.startswith(("[", "<")):  # emotion tag in front of the sentence (ElevenLabs v3, Orpheus, Turbo)
        parts.append("tag " + text.split("]")[0].split(">")[0] + ("]" if text.startswith("[") else ">"))
    elif "<" in text:  # Orpheus tag inside the sentence
        parts.append("tag <" + text.split("<", 1)[1].split(">", 1)[0] + ">")
    return ", ".join(parts) or "-"


def _controls_table(results_dir: Path) -> list[str]:
    """How each engine expressed each emotion, taken from the shared sentence of every run."""
    lines = _header(["Model (setup)", *EMOTIONS])
    for run_dir in sorted(p for p in results_dir.iterdir() if (p / "metrics.csv").exists()):
        by_emotion = {}
        for row in _read_csv(run_dir / "metrics.csv"):
            if row.get("group") == "shared" or row["emotion"] not in by_emotion:
                by_emotion[row["emotion"]] = row.get("settings", "")
        lines.append(_row([run_dir.name, *(_controls(by_emotion[e]) if e in by_emotion else "-" for e in EMOTIONS)]))
    return lines


def summarize(results_dir: Path, listening_dir: Path | None = None) -> str:
    raters, records = collect_ratings(listening_dir)
    out = ["### 1. Speed and resources", "", *_technical_table(results_dir), ""]
    out += [
        "RTF = generation time / audio duration (below 1 is faster than real time; for cloud APIs it "
        f"includes the network). 'Fits in a song': can a {ANNOUNCEMENT_SEC:.0f} s announcement be generated "
        f"while a {SONG_SEC:.0f} s song plays (single listener). Auto emotion match is a rough proxy "
        "(4 classes; it cannot tell happy/excited or neutral/calm apart).",
        "",
    ]
    if records:
        out += [f"### 2. Blind listening scores ({len(raters)} raters: {', '.join(raters)})", ""]
        out += [*_listening_table(raters, records), ""]
        out += [
            "Naturalness: 1 = robotic, 5 = real radio host. Emotion hit: share of clips where the rater "
            "named the intended emotion (chance level with 7 emotions is about 14%). 'Shared sentence': "
            "the same text in every emotion, so only the voice carries the emotion.",
            "",
            "### 3. Listener emotion recognition per emotion",
            "",
            *_emotion_table(records),
            "",
        ]
    else:
        out += ["_No listening ratings yet: run tts_bench.listening and collect the rating sheets._", ""]
    out += [
        "### 4. How each model expressed the emotions",
        "",
        *_controls_table(results_dir),
        "",
        "Values actually used in the runs (shared sentence). tag = emotion tag added to the text.",
        "",
    ]
    if records:
        out += ["### 5. Listener notes (pronunciation and glitches, requirement 6)", "", *_notes_list(records)]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default="results", type=Path)
    parser.add_argument("--listening", default="listening", type=Path)
    args = parser.parse_args(argv)
    listening = args.listening if args.listening.exists() else None
    text = summarize(args.results, listening)
    (args.results / "summary.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
