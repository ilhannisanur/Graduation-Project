"""Rough automatic emotion check with an off-the-shelf speech emotion model.

    python -m tts_bench.score_emotion

This is only a proxy for the comparison: the default model knows 4 acted
classes (neutral, happy, angry, sad) and cannot separate happy/excited or
neutral/calm/serious, and has no class for surprised.
The real quality-control model is built in #21 (DJ Brain).

Writes results/<label>/emotion_scores.csv.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
import soundfile as sf

DEFAULT_MODEL = "superb/wav2vec2-base-superb-er"
TARGET_SR = 16_000
# intended emotion -> coarse class the classifier can recognise
# ("surprised" has no matching class, so it is left out of the automatic score)
COARSE = {
    "neutral": "neu",
    "happy": "hap",
    "excited": "hap",
    "calm": "neu",
    "sad": "sad",
    "serious": "neu",
}


def coarse_label(label: str) -> str:
    return label.strip().lower()[:3]


def load_16k(path: Path) -> np.ndarray:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != TARGET_SR:
        from math import gcd

        from scipy.signal import resample_poly

        g = gcd(sr, TARGET_SR)
        audio = resample_poly(audio, TARGET_SR // g, sr // g).astype(np.float32)
    return audio


def score_results(results_dir: Path, model: str = DEFAULT_MODEL, device: str = "cpu") -> None:
    from transformers import pipeline

    classifier = pipeline("audio-classification", model=model, device=0 if device == "cuda" else -1)
    for metrics in sorted(results_dir.glob("*/metrics.csv")):
        with open(metrics, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        out_rows = []
        for row in rows:
            if row["emotion"] not in COARSE:
                continue
            wav = metrics.parent / f"{row['item_id']}.wav"
            preds = classifier({"raw": load_16k(wav), "sampling_rate": TARGET_SR}, top_k=None)
            scores = {coarse_label(p["label"]): round(float(p["score"]), 4) for p in preds}
            predicted = max(scores, key=scores.get)
            target = COARSE[row["emotion"]]
            out_rows.append(
                {
                    "item_id": row["item_id"],
                    "group": row["group"],
                    "intended": row["emotion"],
                    "target_class": target,
                    "predicted_class": predicted,
                    "match": int(predicted == target),
                    "target_score": scores.get(target, 0.0),
                    **{f"score_{k}": v for k, v in sorted(scores.items())},
                }
            )
        fields = list(out_rows[0].keys()) if out_rows else ["item_id"]
        with open(metrics.parent / "emotion_scores.csv", "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            writer.writerows(out_rows)
        hit = np.mean([r["match"] for r in out_rows]) if out_rows else 0
        print(f"{metrics.parent.name:<22} coarse emotion match: {hit:.0%}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", default="results", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    score_results(args.results, args.model, args.device)


if __name__ == "__main__":
    main()
