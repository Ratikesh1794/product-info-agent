"""Conversation history: list, read and delete the visitor's own conversations."""

from fastapi import APIRouter, HTTPException

from app.db import session as db
from app.schemas.chat import ClientId, SessionDetail, SessionOut
from app.services import history

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionOut])
def list_sessions(client_id: ClientId):
    with db.SessionLocal() as s:
        return history.list_sessions(s, client_id)


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, client_id: ClientId):
    with db.SessionLocal() as s:
        try:
            sess, msgs = history.ui_messages(s, session_id, client_id)
        except history.NotFound:
            raise HTTPException(404, "Conversation not found") from None
        return SessionDetail(id=sess.id, title=sess.title, updated_at=sess.updated_at, messages=msgs)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: str, client_id: ClientId) -> None:
    with db.SessionLocal() as s:
        try:
            history.delete_session(s, session_id, client_id)
        except history.NotFound:
            raise HTTPException(404, "Conversation not found") from None
