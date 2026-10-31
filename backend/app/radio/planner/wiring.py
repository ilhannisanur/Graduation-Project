"""Holds the single planner instance of the application.

The real music source, director and speech client are connected when the backend
starts: ``app.radio.integration.radio_lifespan`` (M1 integration, #12).

If no planner is configured, the endpoints answer 503 instead of using fake data
(team rule: mock data only in tests). Tests configure a planner with fakes.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from .planner import BroadcastPlanner

_planner: BroadcastPlanner | None = None


def configure_planner(planner: BroadcastPlanner | None) -> None:
    global _planner
    _planner = planner


def current_planner() -> BroadcastPlanner | None:
    """The planner if it is connected, else None (for callers that can do without it)."""
    return _planner


def get_planner() -> BroadcastPlanner:
    if _planner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Broadcast planner is not connected to the music, director and "
                "speech services yet (#12)."
            ),
        )
    return _planner


async def shutdown_planner() -> None:
    if _planner is not None:
        await _planner.aclose()
