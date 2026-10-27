"""Holds the single planner instance of the application.

The real music source, director and speech client are connected in the M1
integration (#12), for example in the FastAPI lifespan::

    from app.radio.planner import BroadcastPlanner, configure_planner

    configure_planner(BroadcastPlanner(music=..., director=..., speech=...))

Until then the endpoints answer 503 instead of using fake data (team rule:
mock data only in tests). Tests override ``get_planner`` with fakes.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from .planner import BroadcastPlanner

_planner: BroadcastPlanner | None = None


def configure_planner(planner: BroadcastPlanner | None) -> None:
    global _planner
    _planner = planner


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
