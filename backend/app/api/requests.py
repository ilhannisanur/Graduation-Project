from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.contracts import SongRequest
from app.db.session import get_db
from app.music.requests import service
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


@router.post("", status_code=201)
def create_request(
    body: RequestCreate,
    response: Response,
    user: UserRow = Depends(current_user),
    db: Session = Depends(get_db),
) -> SongRequest:
    try:
        row, created = service.create_request(
            db, user.id, body.raw_text, body.track_id, body.message_readout_allowed
        )
    except service.UnknownTrack:
        raise HTTPException(status_code=404, detail="Track not found") from None
    except service.TooManyPending:
        raise HTTPException(
            status_code=429,
            detail=f"You can have at most {service.MAX_PENDING_PER_USER} requests waiting",
        ) from None
    db.commit()
    if not created:
        response.status_code = 200  # this user already asked for the same song
    return service.to_contract(row, service.estimated_play_times(db).get(row.id))


@router.get("/mine")
def my_requests(
    user: UserRow = Depends(current_user), db: Session = Depends(get_db)
) -> list[SongRequest]:
    times = service.estimated_play_times(db)
    return [service.to_contract(r, times.get(r.id)) for r in service.requests_of_user(db, user.id)]
