from fastapi import APIRouter, FastAPI

from app.api import auth, dj, health, me, tracks
from app.core.logging import setup_logging
from app.radio.integration import radio_lifespan
from app.radio.planner import router as planner_router
from app.speech_client.router import router as speech_router

setup_logging()

# radio_lifespan connects the broadcast planner to music, DJ Brain and the speech service (#12).
app = FastAPI(title="Emotion-Aware AI Radio", lifespan=radio_lifespan)

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(dj.router)
api.include_router(tracks.router)
api.include_router(auth.router)
api.include_router(me.router)
api.include_router(planner_router)
api.include_router(speech_router)
app.include_router(api)
