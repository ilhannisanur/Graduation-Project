"""Announcement audio through the backend (M1 integration, #12).

    GET /api/speech/audio/{name}.wav   an announcement made by the speech service
    GET /api/speech/health             is the speech service up, which engine is running

The speech service listens only on the computer it runs on (127.0.0.1:8001). The
browser therefore never calls it: the planner hands out /api/speech/audio/... URLs
and this router fetches the file from the service. So the player needs one address
for everything (the Vite proxy in development, the phone in the same network, S3's
HLS server later).

Range requests are passed on, so seeking and mobile browsers work as with songs.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings

router = APIRouter(prefix="/speech", tags=["speech"])

# Names the speech service gives its files (content hash). Anything else is refused
# here, so this route can never be used to reach other paths on the service.
AUDIO_NAME = re.compile(r"[0-9a-f]{32}\.wav")
PASSED_HEADERS = ("content-type", "content-length", "content-range", "accept-ranges", "etag")
HEALTH_TIMEOUT_S = 3.0
AUDIO_TIMEOUT_S = 15.0


async def speech_http() -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client for the speech service; tests replace it with a fake transport."""
    async with httpx.AsyncClient(
        base_url=get_settings().speech_service_url, timeout=AUDIO_TIMEOUT_S
    ) as client:
        yield client


@router.get("/audio/{name}")
async def announcement_audio(
    name: str, request: Request, client: httpx.AsyncClient = Depends(speech_http)
) -> Response:
    if not AUDIO_NAME.fullmatch(name):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Audio not found")
    headers = {"Range": request.headers["range"]} if "range" in request.headers else {}
    try:
        upstream = await client.get(f"/audio/{name}", headers=headers)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="Speech service is not reachable"
        ) from exc
    if upstream.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Audio not found")
    if upstream.status_code not in (status.HTTP_200_OK, status.HTTP_206_PARTIAL_CONTENT):
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=f"Speech service answered {upstream.status_code}",
        )
    passed = {key: upstream.headers[key] for key in PASSED_HEADERS if key in upstream.headers}
    # The name is the hash of the content: the same URL never changes, so it may be cached.
    passed["cache-control"] = "public, max-age=86400, immutable"
    return Response(content=upstream.content, status_code=upstream.status_code, headers=passed)


@router.get("/health")
async def speech_health(client: httpx.AsyncClient = Depends(speech_http)) -> JSONResponse:
    """The speech service's own /health, or 503 with the reason if it cannot be reached."""
    try:
        upstream = await client.get("/health", timeout=HEALTH_TIMEOUT_S)
        body = upstream.json()
    except (httpx.HTTPError, ValueError):
        return JSONResponse(
            {
                "status": "down",
                "detail": f"speech service not reachable at {client.base_url}",
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    code = status.HTTP_200_OK if upstream.is_success else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(body, status_code=code)
