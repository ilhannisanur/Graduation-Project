from fastapi import APIRouter, FastAPI

from app.api import auth, dj, health, me, tracks
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(title="Emotion-Aware AI Radio")

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(dj.router)
api.include_router(tracks.router)
api.include_router(auth.router)
api.include_router(me.router)
app.include_router(api)
