"""Conversation history repository: everything that touches the sessions/chats tables."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as Db

from app.db.models import Chat, ChatSession


class NotFound(Exception):
    """Missing session, or one that belongs to another client (indistinguishable on purpose)."""


def _owned(db: Db, session_id: str, client_id: str) -> ChatSession | None:
    s = db.get(ChatSession, session_id)
    if s and s.client_id != client_id:
        raise NotFound
    return s


def load_messages(db: Db, session_id: str, client_id: str) -> list[dict]:
    """Prior turns in OpenAI chat format (no system prompt), for replaying into the model."""
    s = _owned(db, session_id, client_id)
    if not s:
        return []
    out = []
    for c in s.chats:
        m: dict = {"role": c.role, "content": c.content}
        if c.tool_calls:
            m["tool_calls"] = c.tool_calls
        if c.tool_call_id:
            m["tool_call_id"] = c.tool_call_id
        out.append(m)
    return out


def save_turn(db: Db, session_id: str, client_id: str, messages: list[dict], meta: dict) -> None:
    """Persist one completed turn atomically. `meta` goes on the turn's final assistant message."""
    s = _owned(db, session_id, client_id)
    if not s:
        first = next(m["content"] for m in messages if m["role"] == "user")
        s = ChatSession(id=session_id, client_id=client_id, title=_title(first))
        db.add(s)
    for i, m in enumerate(messages):
        db.add(Chat(
            session_id=session_id,
            role=m["role"],
            content=m.get("content"),
            tool_calls=m.get("tool_calls"),
            tool_call_id=m.get("tool_call_id"),
            meta=meta if i == len(messages) - 1 and m["role"] == "assistant" else None,
        ))
    db.flush()
    db.execute(update(ChatSession).where(ChatSession.id == session_id).values(updated_at=func.now()))
    db.commit()


def list_sessions(db: Db, client_id: str, limit: int = 50) -> list[ChatSession]:
    q = select(ChatSession).where(ChatSession.client_id == client_id).order_by(ChatSession.updated_at.desc()).limit(limit)
    return list(db.scalars(q))


def ui_messages(db: Db, session_id: str, client_id: str) -> tuple[ChatSession, list[dict]]:
    """History shaped for the chat UI: user messages and final answers (tool plumbing folded into meta)."""
    s = _owned(db, session_id, client_id)
    if not s:
        raise NotFound
    msgs = []
    for c in s.chats:
        if c.role == "user":
            msgs.append({"id": str(c.id), "role": "user", "text": c.content or "", "products": [], "steps": []})
        elif c.role == "assistant" and not c.tool_calls:
            meta = c.meta or {}
            msgs.append({"id": str(c.id), "role": "assistant", "text": c.content or "",
                         "products": meta.get("products", []), "steps": meta.get("steps", [])})
    return s, msgs


def delete_session(db: Db, session_id: str, client_id: str) -> None:
    if s := _owned(db, session_id, client_id):
        db.delete(s)
        db.commit()


def _title(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= 80 else text[:77].rstrip() + "…"

