"""Prepare a blind listening test from the generated clips.

    python -m tts_bench.listening --raters azra nisa nisanur

Creates:
  listening/clips/<clip_id>.wav    anonymised copies (engine names hidden)
  listening/rating_<rater>.xlsx    one sheet per rater, each in a different random order
  listening/key.csv                which clip is which; do not open before rating is done

Share the whole listening folder (clips + the rater's own sheet). Each rater
clicks a clip id to play it and fills two columns using the drop-down lists:
  naturalness        1 (robotic) ... 5 (sounds like a real radio host)
  perceived_emotion  one of the emotion labels
"""

from __future__ import annotations

import argparse
import csv
import random
import shutil
from pathlib import Path

from .engines.base import EMOTIONS

RATING_FIELDS = ["clip_id", "naturalness", "perceived_emotion", "notes"]
KEY_FIELDS = ["clip_id", "label", "item_id", "group", "emotion"]
SUBSETS = ("listen", "shared", "content", "all")


def _read_metrics(results_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for metrics in sorted(results_dir.glob("*/metrics.csv")):
        with open(metrics, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                row["_wav"] = str(metrics.parent / f"{row['item_id']}.wav")
                rows.append(row)
    return rows


def _select(rows: list[dict[str, str]], subset: str) -> list[dict[str, str]]:
    if subset == "listen":
        return [r for r in rows if str(r.get("listen", "0")) == "1"]
    if subset in ("shared", "content"):
        return [r for r in rows if r["group"] == subset]
    return rows


def write_rating_sheet(path: Path, clip_ids: list[str], rater: str) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "ratings"
    ws.append(RATING_FIELDS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
    for i, cid in enumerate(clip_ids, start=2):
        ws.cell(row=i, column=1, value=cid)
        ws.cell(row=i, column=1).hyperlink = f"clips/{cid}.wav"  # click to play
        ws.cell(row=i, column=1).font = Font(color="0563C1", underline="single")

    last = len(clip_ids) + 1
    nat = DataValidation(type="whole", operator="between", formula1="1", formula2="5", allow_blank=True)
    nat.error = "Enter a whole number from 1 to 5"
    emo = DataValidation(type="list", formula1='"' + ",".join(EMOTIONS) + '"', allow_blank=True)
    ws.add_data_validation(nat)
    ws.add_data_validation(emo)
    nat.add(f"B2:B{last}")
    emo.add(f"C2:C{last}")
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 50
    ws.freeze_panes = "A2"

    guide = wb.create_sheet("guide")
    for line in (
        f"Rater: {rater}",
        "Click a clip id to play it. Listen to every clip once in this order, without going back.",
        "naturalness: 1 = robotic, 3 = acceptable, 5 = sounds like a real radio host.",
        f"perceived_emotion: the emotion you hear in the VOICE, one of: {', '.join(EMOTIONS)}.",
        "Ignore whether the words fit the emotion; judge only how it sounds.",
        "notes: write any mispronounced word or glitch (cut-off, noise, wrong stress), e.g. 'Ankara wrong'.",
        "Do not open key.csv and do not talk about the clips until everyone has finished.",
    ):
        guide.append([line])
    guide.column_dimensions["A"].width = 110
    wb.save(path)


def read_rating_sheet(path: Path) -> list[dict[str, str]]:
    """Read a filled sheet (.xlsx, or .csv for anyone who used a text editor)."""
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig") as fh:
            sample = fh.read(2048)
            fh.seek(0)
            delimiter = ";" if sample.count(";") > sample.count(",") else ","
            return list(csv.DictReader(fh, delimiter=delimiter))
    from openpyxl import load_workbook

    ws = load_workbook(path, read_only=True, data_only=True)["ratings"]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]
    return [{h: "" if v is None else str(v) for h, v in zip(header, r, strict=False)} for r in rows[1:] if r[0]]


def build_listening_test(
    results_dir: Path,
    out_dir: Path,
    raters: list[str],
    subset: str = "listen",
    labels: list[str] | None = None,
    seed: int = 7,
) -> list[dict[str, str]]:
    rows = _select(_read_metrics(results_dir), subset)
    if labels:
        rows = [r for r in rows if r["label"] in labels]
    rows = [r for r in rows if Path(r["_wav"]).exists()]
    if not rows:
        raise SystemExit(f"No clips found under {results_dir}. Run tts_bench.run first.")

    rng = random.Random(seed)
    ids = rng.sample(range(1000, 10000), len(rows))
    out_dir.mkdir(parents=True, exist_ok=True)
    clips_dir = out_dir / "clips"
    if clips_dir.exists():
        shutil.rmtree(clips_dir)
    clips_dir.mkdir()

    key: list[dict[str, str]] = []
    for clip_num, row in zip(ids, rows, strict=True):
        clip_id = f"c{clip_num}"
        shutil.copyfile(row["_wav"], clips_dir / f"{clip_id}.wav")
        key.append({"clip_id": clip_id, **{k: row[k] for k in KEY_FIELDS if k != "clip_id"}})

    with open(out_dir / "key.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=KEY_FIELDS)
        writer.writeheader()
        writer.writerows(sorted(key, key=lambda r: r["clip_id"]))

    for rater in raters:
        order = [k["clip_id"] for k in key]
        rng.shuffle(order)
        write_rating_sheet(out_dir / f"rating_{rater}.xlsx", order, rater)
    return key


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default="results", type=Path)
    parser.add_argument("--out", default="listening", type=Path)
    parser.add_argument("--raters", nargs="+", default=["azra", "nisa", "nisanur"])
    parser.add_argument(
        "--only",
        choices=SUBSETS,
        default="listen",
        help="listen (default): 2 items per emotion; shared: only the same-text sentence; all: everything",
    )
    parser.add_argument("--labels", nargs="+", help="only these result folders")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)
    key = build_listening_test(args.results, args.out, args.raters, args.only, args.labels, args.seed)
    models = sorted({k["label"] for k in key})
    print(f"{len(key)} clips from {len(models)} models ({', '.join(models)}) -> {args.out / 'clips'}")
    print("Sheets: " + ", ".join(f"rating_{r}.xlsx" for r in args.raters))
    print("Next: python -m tts_bench.listening_page --raters " + " ".join(args.raters) + "  (one HTML page per rater)")


if __name__ == "__main__":
    main()
