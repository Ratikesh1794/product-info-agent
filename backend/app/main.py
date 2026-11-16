from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, health
from app.core.config import settings
from app.services.catalog import get_catalog

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_catalog()  # load + validate the CSV at boot, not on the first user's request
    if settings.auto_migrate:
        command.upgrade(Config(str(ALEMBIC_INI)), "head")  # one-click dev: schema is always current
    yield


app = FastAPI(title="Product Info Agent", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
