import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.content.dj.song_intro import fallback_song_intro, generate_song_intro
from app.content.llm import LLMClient, LLMError, get_llm_client
from app.contracts import Emotion, Track

router = APIRouter(prefix="/dj")

DJ_SYSTEM = (
    "You are the host of an English-language radio station. "
    "Write short, warm, natural spoken announcements. No emojis, no stage directions."
)


class SongInfo(BaseModel):
    title: str
    artist: str
    mood: str


class DJPreview(BaseModel):
    announcement: str


def llm_dependency() -> LLMClient:
    try:
        return get_llm_client()
    except LLMError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/preview")
def preview(song: SongInfo, llm: LLMClient = Depends(llm_dependency)) -> DJPreview:
    prompt = (
        "Introduce the next song in two or three sentences. "
        f"Title: {song.title}. Artist: {song.artist}. Mood: {song.mood}."
    )
    try:
        return DJPreview(announcement=llm.generate_text(prompt, system=DJ_SYSTEM).strip())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# --- Song intro preview (#59) ---
# Runs the real DJ Brain song intro (the same code the broadcast planner uses) and
# reports what was sent to the LLM and how long it took. For trying prompts and
# measuring LLM speed separately from TTS.

PREVIEW_DURATION_SECONDS = 180.0  # not used by the prompt; Track needs a value


class PreviewSong(BaseModel):
    title: str = Field(min_length=1)
    artist: str = Field(min_length=1)
    valence: float | None = Field(default=None, ge=0, le=1)
    arousal: float | None = Field(default=None, ge=0, le=1)


class SongIntroPreviewRequest(BaseModel):
    next_track: PreviewSong
    previous_track: PreviewSong | None = None
    recent_announcements: list[str] = Field(default_factory=list, max_length=3)


class LLMCall(BaseModel):
    duration_ms: int
    ok: bool  # False when the client raised LLMError (after its own retries)


class SongIntroPreview(BaseModel):
    text: str
    emotion: Emotion
    target_seconds: float
    used_fallback: bool
    prompt: str | None  # the per-request prompt; the fixed rules are in song_intro.txt
    llm_ms: int  # total time spent waiting for the LLM
    llm_calls: list[LLMCall]


class RecordingLLM(LLMClient):
    """Wraps a real client and notes the prompt, duration and outcome of every call."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner
        self.prompts: list[str] = []
        self.calls: list[LLMCall] = []

    def generate_text(self, prompt: str, system: str | None = None) -> str:
        return self._timed(self._inner.generate_text, prompt, system)

    def generate_json(self, prompt: str, system: str | None = None) -> dict[str, Any]:
        return self._timed(self._inner.generate_json, prompt, system)

    def _timed(self, call: Any, prompt: str, system: str | None) -> Any:
        self.prompts.append(prompt)
        start = time.perf_counter()
        ok = False
        try:
            result = call(prompt, system=system)
            ok = True
            return result
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000)
            self.calls.append(LLMCall(duration_ms=duration_ms, ok=ok))


def _preview_track(song: PreviewSong, track_id: str) -> Track:
    return Track(
        id=track_id,
        title=song.title,
        artist=song.artist,
        duration_seconds=PREVIEW_DURATION_SECONDS,
        license="unknown",
        license_url="",
        source_url="",
        valence=song.valence,
        arousal=song.arousal,
    )


@router.post("/song-intro-preview")
def song_intro_preview(
    body: SongIntroPreviewRequest, llm: LLMClient = Depends(llm_dependency)
) -> SongIntroPreview:
    next_track = _preview_track(body.next_track, "preview-next")
    previous_track = (
        _preview_track(body.previous_track, "preview-previous") if body.previous_track else None
    )
    recorder = RecordingLLM(llm)

    spec = generate_song_intro(
        recorder,
        next_track,
        previous_track=previous_track,
        recent_announcements=body.recent_announcements,
    )

    return SongIntroPreview(
        text=spec.text,
        emotion=spec.emotion,
        target_seconds=spec.target_seconds,
        # generate_song_intro never raises; a fallback is recognised by its template.
        used_fallback=spec == fallback_song_intro(next_track),
        prompt=recorder.prompts[0] if recorder.prompts else None,
        llm_ms=sum(call.duration_ms for call in recorder.calls),
        llm_calls=recorder.calls,
    )
