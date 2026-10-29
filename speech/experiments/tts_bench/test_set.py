from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .engines.base import EMOTIONS, SynthesisRequest

DEFAULT_TEST_SET = Path(__file__).with_name("test_set.json")


@dataclass(frozen=True)
class BenchItem:
    id: str
    group: str  # "shared" or "content"
    request: SynthesisRequest
    listen: bool = False  # included in the blind listening test


def load_test_set(path: str | Path = DEFAULT_TEST_SET) -> list[BenchItem]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    default_intensity = float(data.get("default_intensity", 0.5))
    items: list[BenchItem] = []
    seen: set[str] = set()
    for raw in data["items"]:
        if raw["id"] in seen:
            raise ValueError(f"Duplicate test item id: {raw['id']}")
        seen.add(raw["id"])
        if raw["emotion"] not in EMOTIONS:
            raise ValueError(f"{raw['id']}: unknown emotion {raw['emotion']!r}")
        req = SynthesisRequest(
            text=raw["text"],
            emotion=raw["emotion"],
            intensity=float(raw.get("intensity", default_intensity)),
        )
        items.append(
            BenchItem(
                id=raw["id"],
                group=raw.get("group", "content"),
                request=req,
                listen=bool(raw.get("listen", False)),
            )
        )
    return items
