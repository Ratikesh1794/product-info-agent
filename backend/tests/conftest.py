import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

import app.db.models  # noqa: F401  (registers tables)
from app.db import session as db
from app.db.base import Base

TEST_DB = os.getenv("TEST_DATABASE_URL", "postgresql+psycopg://localhost:5432/product_agent_test")


@pytest.fixture
def test_db(monkeypatch):
    """Real Postgres (JSONB, cascades, check constraints), fresh schema per test."""
    engine = create_engine(TEST_DB)
    try:
        engine.connect().close()
    except OperationalError:
        pytest.skip(f"test database not reachable: {TEST_DB}")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "SessionLocal", sessionmaker(engine, expire_on_commit=False))
    yield db.SessionLocal
    engine.dispose()
