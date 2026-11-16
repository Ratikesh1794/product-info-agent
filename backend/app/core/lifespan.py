from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.core.config import settings
from app.services.catalog import get_catalog

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@asynccontextmanager
async def lifespan(_: FastAPI):
    get_catalog()  # load + validate the CSV at boot, not on the first user's request
    if settings.auto_migrate:
        command.upgrade(Config(str(ALEMBIC_INI)), "head")  # one-click dev: schema is always current
    yield
