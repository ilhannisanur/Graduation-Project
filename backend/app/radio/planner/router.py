"""HTTP API of the broadcast planner (S2: pull-based; S3 replaces it with HLS).

    POST   /api/sessions                    start a listening session
    GET    /api/sessions/{session_id}/next  segment to play now
    DELETE /api/sessions/{session_id}       stop the session

The player calls /next when the current segment ends. The next segment is
prepared in the background meanwhile, so the call returns immediately.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from .models import CreateSessionRequest, NextSegmentResponse, SessionCreated
from .planner import (
    BroadcastPlanner,
    NoTrackAvailable,
    SessionNotFound,
    TooManySessions,
)
from .wiring import get_planner

router = APIRouter(prefix="/sessions", tags=["broadcast"])

PlannerDep = Annotated[BroadcastPlanner, Depends(get_planner)]


@router.post("", response_model=SessionCreated, status_code=status.HTTP_201_CREATED)
async def create_session(
    planner: PlannerDep,
    body: CreateSessionRequest | None = None,
) -> SessionCreated:
    body = body or CreateSessionRequest()
    try:
        session = planner.create_session(user_id=body.user_id)
    except TooManySessions as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return SessionCreated(session_id=session.session_id, user_id=session.user_id)


@router.get("/{session_id}/next", response_model=NextSegmentResponse)
async def next_segment(
    session_id: str,
    planner: PlannerDep,
) -> NextSegmentResponse:
    try:
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
) -> Response:
    try:
        planner.close_session(session_id)
    except SessionNotFound as exc:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Session not found or expired"
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
