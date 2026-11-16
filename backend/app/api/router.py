"""Single place where every route module is mounted under /api."""

from fastapi import APIRouter

from app.api.routes import chat, health, sessions

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(sessions.router)
