"""Declarative base shared by all models, plus column types used across them."""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# JSONB on Postgres, JSON elsewhere. none_as_null: Python None must be SQL NULL, not a JSON 'null' value.
JsonType = JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
