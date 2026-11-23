"""The studio screen: the station's mood, the mood map and the links for phones.

GET  /api/station/moods             mood presets and the current one
POST /api/station/mood              set the station's mood (login required)
GET  /api/station/map               every track on the valence/energy plane
GET  /api/station/info              the address phones use to send a request
GET  /api/station/emotions          voice samples, one per emotion (data/demo/emotions)
GET  /api/station/emotions/{file}   one sample's audio
"""

import json
import socket
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.core.config import PROJECT_ROOT, get_settings
from app.db.session import get_db
from app.music.models import TrackRow
from app.music.mood_target import PRESETS, MoodTarget, current_target, set_target
from app.radio.planner import current_planner
from app.users import UserRow

router = APIRouter(prefix="/station", tags=["station"])

EMOTIONS_DIR = PROJECT_ROOT / "data" / "demo" / "emotions"


class Mood(BaseModel):
    id: str
    label: str
    valence: float
    energy: float
    reason: str


class Moods(BaseModel):
    presets: list[Mood]
    current: Mood | None


class MoodChoice(BaseModel):
    id: str | None


class MapPoint(BaseModel):
    id: str
    title: str
    artist: str
    valence: float
    energy: float
    tags: list[str]


class StationInfo(BaseModel):
    request_url: str


class EmotionSample(BaseModel):
    emotion: str
    label: str
    text: str
    file: str


def _mood(target: MoodTarget | None) -> Mood | None:
    return None if target is None else Mood(**target.__dict__)


@router.get("/moods")
def moods() -> Moods:
    return Moods(presets=[_mood(t) for t in PRESETS.values()], current=_mood(current_target()))


async def _replan() -> None:
    planner = current_planner()
    if planner is not None:
        planner.refresh_upcoming()


@router.post("/mood")
def choose_mood(
    choice: MoodChoice, background: BackgroundTasks, user: UserRow = Depends(current_user)
) -> Moods:
    try:
        set_target(choice.id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown mood") from None
    background.add_task(_replan)  # the next song follows the new mood
    return moods()


@router.get("/map")
def mood_map(db: Session = Depends(get_db)) -> list[MapPoint]:
    rows = db.scalars(
        select(TrackRow)
        .where(TrackRow.valence.is_not(None), TrackRow.arousal.is_not(None))
        .order_by(TrackRow.id)
    )
    return [
        MapPoint(
            id=r.id,
            title=r.title,
            artist=r.artist,
            valence=r.valence,
            energy=r.arousal,
            tags=r.mood_tags,
        )
        for r in rows
    ]


def _lan_address() -> str | None:
    """This computer's address on the local network (no packet is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            address = s.getsockname()[0]
    except OSError:
        return None
    return None if address.startswith("127.") else address


@router.get("/info")
def station_info() -> StationInfo:
    base = get_settings().public_web_url.rstrip("/")
    if not base:
        address = _lan_address()
        base = f"http://{address}:5173" if address else "http://localhost:5173"
    return StationInfo(request_url=f"{base}/#/request")


def _emotion_manifest() -> list[EmotionSample]:
    path = EMOTIONS_DIR / "manifest.json"
    if not path.is_file():
        return []
    samples = [EmotionSample(**item) for item in json.loads(path.read_text(encoding="utf-8"))]
    return [s for s in samples if (EMOTIONS_DIR / s.file).is_file()]


@router.get("/emotions")
def emotion_samples() -> list[EmotionSample]:
    return _emotion_manifest()


@router.get("/emotions/{file}")
def emotion_audio(file: str) -> FileResponse:
    known = {s.file for s in _emotion_manifest()}
    if file not in known:  # only files listed in the manifest, never arbitrary paths
        raise HTTPException(status_code=404, detail="Sample not found")
    path: Path = EMOTIONS_DIR / file
    return FileResponse(path, media_type="audio/wav")
