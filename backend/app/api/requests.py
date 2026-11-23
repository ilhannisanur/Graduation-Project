from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.contracts import SongRequest
from app.db.session import get_db
from app.music.requests import service
from app.radio.planner import current_planner
from app.users import UserRow

router = APIRouter(prefix="/requests")


class RequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    # A catalog track the listener picked (e.g. from GET /api/tracks?q=). Without it the text
    # waits for DJ Brain (#13) to work out what was asked.
    track_id: str | None = None
    # Explicit permission to read the message in the request out on air.
    message_readout_allowed: bool = False
    # Name for the DJ to say on air, chosen by the listener (not the username).
    on_air_name: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)
    ] = None
    # A short message for the DJ; read on air only with message_readout_allowed.
    message: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ] = None


class QueueItem(BaseModel):
    position: int
    track_id: str
    title: str
    artist: str
    requests: int
    on_air_names: list[str]
    messages: list[str]
    estimated_play_time: datetime


@router.post("", status_code=201)
def create_request(
    body: RequestCreate,
    response: Response,
    background: BackgroundTasks,
    user: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
) -> SongRequest:
    try:
        row, created = service.create_request(
            db,
            user.id,
            body.raw_text,
            body.track_id,
            body.message_readout_allowed,
            on_air_name=body.on_air_name,
            message=body.message,
        )
    except service.UnknownTrack:
        raise HTTPException(status_code=404, detail="Track not found") from None
    except service.TooManyPending:
        raise HTTPException(
            status_code=429,
            detail=f"You can have at most {service.MAX_PENDING_PER_USER} requests waiting",
        ) from None
    db.commit()
    if created and row.track_id:
        # Plan the request into the broadcast now, not two songs later.
        background.add_task(refresh_broadcast)
    if not created:
        response.status_code = 200  # this user already asked for the same song
    return service.to_contract(row, service.estimated_play_times(db).get(row.id))


async def refresh_broadcast() -> None:
    planner = current_planner()
    if planner is not None:
        planner.refresh_upcoming()


@router.get("/queue")
def queue(db: Session = Depends(get_db)) -> list[QueueItem]:
    """The shared request queue; public, it shows no user ids, only chosen on-air names."""
    return [QueueItem(**item) for item in service.public_queue(db)]


@router.get("/mine")
def my_requests(
    user: UserRow = Depends(current_user), db: Session = Depends(get_db)
) -> list[SongRequest]:
    times = service.estimated_play_times(db)
    return [service.to_contract(r, times.get(r.id)) for r in service.requests_of_user(db, user.id)]
