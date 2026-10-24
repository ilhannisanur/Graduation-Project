from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.content.llm import LLMClient, LLMError, get_llm_client

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
