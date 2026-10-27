"""HTTP API of the broadcast planner (S2: pull-based; S3 replaces it with HLS).

    POST   /api/sessions                    start a listening session
    GET    /api/sessions/{session_id}/next  segment to play now
    DELETE /api/sessions/{session_id}       stop the session

The player calls /next when the current segment ends. The next segment is
prepared in the background meanwhile, so the call returns immediately.

The listener comes from the login cookie (#15), never from the request: a
logged-in user's session belongs to that account, anyone else gets 404 for it.
Without a login the session is a guest session.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.auth import optional_user
from app.users import UserRow

from .models import NextSegmentResponse, SessionCreated
from .planner import (
    BroadcastPlanner,
    NoTrackAvailable,
    SessionNotFound,
    TooManySessions,
)
from .wiring import get_planner

router = APIRouter(prefix="/sessions", tags=["broadcast"])

GUEST = "guest"

PlannerDep = Annotated[BroadcastPlanner, Depends(get_planner)]
UserDep = Annotated[UserRow | None, Depends(optional_user)]


def _check_owner(planner: BroadcastPlanner, session_id: str, user: UserRow | None) -> None:
    """Raise SessionNotFound unless the caller may use this session.

    Guest sessions are open to whoever holds the (random, unguessable) session id. An
    account's session answers 404, not 403, to others so it does not reveal that it exists.
    """
    owner = planner.get_session(session_id).user_id
    if owner != GUEST and (user is None or user.id != owner):
        raise SessionNotFound(session_id)


@router.post("", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(planner: PlannerDep, user: UserDep) -> SessionCreated:
    try:
        session = planner.create_session(user_id=user.id if user else GUEST)
    except TooManySessions as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return SessionCreated(session_id=session.session_id, user_id=session.user_id)


@router.get("/{session_id}/next", response_model=NextSegmentResponse)
async def next_segment(
    session_id: str,
    planner: PlannerDep,
    user: UserDep,
) -> NextSegmentResponse:
    try:
        _check_owner(planner, session_id, user)
        return await planner.next_segment(session_id)
    except SessionNotFound as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Session not found or expired"
        ) from exc
    except NoTrackAvailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="No song available right now"
        ) from exc


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def close_session(
    session_id: str,
    planner: PlannerDep,
    user: UserDep,
) -> Response:
    try:
        _check_owner(planner, session_id, user)
        planner.close_session(session_id)
    except SessionNotFound as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Session not found or expired"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
