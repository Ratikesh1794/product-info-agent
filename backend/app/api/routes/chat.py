import json
import logging
from collections.abc import Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError

from app.db import session as db
from app.schemas.chat import ChatRequest, ClientId
from app.services import agent, history

router = APIRouter(tags=["chat"])
log = logging.getLogger(__name__)


def _sse(ev: dict) -> str:
    return f"event: {ev['type']}\ndata: {json.dumps(ev)}\n\n"


@router.post("/chat")
def chat(req: ChatRequest, client_id: ClientId = "anonymous") -> StreamingResponse:
    """Streams agent events as SSE (token, tool_call, tool_result, products, error, done).

    The turn is written to Postgres only once it completes, in one transaction: a failed or abandoned turn
    leaves no half-saved history behind.
    """
    with db.SessionLocal() as s:
        prior = history.load_messages(s, req.session_id)

    session = agent.Session(prior)
    start = len(session.messages)

    def stream() -> Iterator[str]:
        steps: list[dict] = []
        products: list[dict] = []
        failed = False
        for ev in agent.run_turn(session, req.message.strip()):
            match ev["type"]:
                case "tool_call":
                    steps.append({"name": ev["name"], "args": ev["args"]})
                case "tool_result":
                    step = next(s for s in steps if s["name"] == ev["name"] and "ms" not in s)
                    step.update(summary=ev["summary"], ms=ev["ms"])
                case "products":
                    products = ev["items"]
                case "error":
                    failed = True
                case "done" if not failed:
                    try:
                        with db.SessionLocal() as s:
                            history.save_turn(s, req.session_id, client_id, session.messages[start:],
                                              {"products": products, "steps": steps})
                    except SQLAlchemyError:
                        log.exception("saving turn failed")
                        yield _sse({"type": "error", "message": "This answer couldn’t be saved to your history."})
            yield _sse(ev)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

