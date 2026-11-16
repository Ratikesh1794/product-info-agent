from datetime import datetime
from typing import Annotated

from fastapi import Header
from pydantic import BaseModel, Field

Id = Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]

# Anonymous browser id (no auth in this demo): scopes which conversations a visitor can list/read/delete.
ClientId = Annotated[str, Header(alias="X-Client-Id", min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]


class ChatRequest(BaseModel):
    session_id: Id
    message: str = Field(min_length=1, max_length=2000)


class SessionOut(BaseModel):
    id: str
    title: str
    updated_at: datetime


class SessionDetail(SessionOut):
    messages: list[dict]
