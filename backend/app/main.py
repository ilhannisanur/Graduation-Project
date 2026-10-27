from fastapi import APIRouter, FastAPI

from app.api import dj, health, tracks
from app.core.logging import setup_logging
from app.radio.planner import router as planner_router

setup_logging()

app = FastAPI(title="Emotion-Aware AI Radio")

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(dj.router)
api.include_router(tracks.router)
api.include_router(planner_router)
app.include_router(api)
