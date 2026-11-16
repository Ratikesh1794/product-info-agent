import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Chat
from app.main import app
from app.services import agent

client = TestClient(app)
ME = {"X-Client-Id": "client-aaaa-1111"}
OTHER = {"X-Client-Id": "client-bbbb-2222"}


def fake_turn(reply: str, with_tool: bool = True, fail: bool = False):
    """Stand-in for agent.run_turn: appends what the real loop would append and yields the same events."""

    def run_turn(session, message):
        session.messages.append({"role": "user", "content": message})
        if with_tool:
            call = {"id": "call_1", "type": "function", "function": {"name": "get_product", "arguments": '{"model_number":"GBA18V20"}'}}
            session.messages.append({"role": "assistant", "content": None, "tool_calls": [call]})
            yield {"type": "tool_call", "name": "get_product", "args": call["function"]["arguments"]}
            session.messages.append({"role": "tool", "tool_call_id": "call_1", "content": '{"found": true}'})
            yield {"type": "tool_result", "name": "get_product", "ms": 3, "summary": "ok"}
        if fail:
            yield {"type": "error", "message": "LLM request failed"}
            yield {"type": "done"}
            return
        session.messages.append({"role": "assistant", "content": reply})
        yield {"type": "token", "text": reply}
        yield {"type": "products", "items": [{"model_number": "GBA18V20"}]}
        yield {"type": "done"}

    return run_turn


def events(r) -> list[dict]:
    return [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]


def post(msg: str, sid: str = "session-0001", headers=ME):
    return client.post("/api/chat", json={"session_id": sid, "message": msg}, headers=headers)


def test_chat_streams_and_persists_turn(test_db, monkeypatch):
    monkeypatch.setattr(agent, "run_turn", fake_turn("It's $109."))
    r = post("  How much is the GBA18V20?  ")
    assert r.headers["content-type"].startswith("text/event-stream")
    assert [e["type"] for e in events(r)] == ["tool_call", "tool_result", "token", "products", "done"]

    with test_db() as s:
        rows = list(s.scalars(select(Chat).order_by(Chat.id)))
    assert [c.role for c in rows] == ["user", "assistant", "tool", "assistant"]
    assert rows[0].content == "How much is the GBA18V20?"
    assert rows[1].tool_calls[0]["id"] == "call_1" and rows[2].tool_call_id == "call_1"
    assert rows[3].meta["steps"][0] == {"name": "get_product", "args": '{"model_number":"GBA18V20"}', "summary": "ok", "ms": 3}


def test_history_is_replayed_into_the_next_turn(test_db, monkeypatch):
    monkeypatch.setattr(agent, "run_turn", fake_turn("First."))
    post("first question")
    seen = {}

    def capture(session, message):
        seen["roles"] = [m["role"] for m in session.messages]
        yield from fake_turn("Second.", with_tool=False)(session, message)

    monkeypatch.setattr(agent, "run_turn", capture)
    post("second question")
    assert seen["roles"] == ["system", "user", "assistant", "tool", "assistant"]


def test_failed_turn_is_not_saved(test_db, monkeypatch):
    monkeypatch.setattr(agent, "run_turn", fake_turn("x", fail=True))
    post("hello")
    assert client.get("/api/sessions", headers=ME).json() == []


def test_sessions_list_detail_delete(test_db, monkeypatch):
    monkeypatch.setattr(agent, "run_turn", fake_turn("It's $109."))
    post("How much is the GBA18V20 battery?", sid="session-0001")
    post("Second conversation", sid="session-0002")

    listed = client.get("/api/sessions", headers=ME).json()
    assert [s["id"] for s in listed] == ["session-0002", "session-0001"]  # most recent first
    assert listed[1]["title"] == "How much is the GBA18V20 battery?"

    detail = client.get("/api/sessions/session-0001", headers=ME).json()
    assert [(m["role"], m["text"]) for m in detail["messages"]] == [("user", "How much is the GBA18V20 battery?"), ("assistant", "It's $109.")]
    assert detail["messages"][1]["products"] == [{"model_number": "GBA18V20"}]
    assert detail["messages"][1]["steps"][0]["name"] == "get_product"

    assert client.delete("/api/sessions/session-0001", headers=ME).status_code == 204
    assert [s["id"] for s in client.get("/api/sessions", headers=ME).json()] == ["session-0002"]
    with test_db() as s:  # chats cascade-deleted with their session
        assert {c.session_id for c in s.scalars(select(Chat))} == {"session-0002"}


def test_history_is_shared_across_browsers(test_db, monkeypatch):
    monkeypatch.setattr(agent, "run_turn", fake_turn("x"))
    post("mine")
    assert [s["id"] for s in client.get("/api/sessions", headers=OTHER).json()] == ["session-0001"]
    assert client.get("/api/sessions").status_code == 200  # no client id needed
    assert client.get("/api/sessions/session-0001", headers=OTHER).status_code == 200
    assert client.get("/api/sessions/missing-0001").status_code == 404
    assert post("continue from another browser", headers=OTHER).status_code == 200
    assert client.delete("/api/sessions/session-0001", headers=OTHER).status_code == 204


def test_rejects_bad_input():
    assert post("hi", sid="x").status_code == 422
    assert post("").status_code == 422
    assert post("a" * 2001).status_code == 422


def test_disconnect_mid_turn_rolls_back_history(monkeypatch):
    monkeypatch.setattr(agent, "run_tool", lambda name, args: {"found": True})

    class FakeStream:
        def __iter__(self):
            fn = type("F", (), {"name": "get_product", "arguments": "{}"})
            tc = type("T", (), {"index": 0, "id": "call_1", "function": fn})
            delta = type("D", (), {"content": None, "tool_calls": [tc]})
            return iter([type("C", (), {"choices": [type("Ch", (), {"delta": delta})]})])

    fake = type("O", (), {"chat": type("Ch", (), {"completions": type("Co", (), {"create": staticmethod(lambda **k: FakeStream())})})})
    monkeypatch.setattr(agent, "_openai", lambda: fake)
    s = agent.Session()
    gen = agent.run_turn(s, "hi")
    assert next(gen)["type"] == "tool_call"  # tool requested, result not yet appended
    gen.close()  # client disconnects here
    assert [m["role"] for m in s.messages] == ["system"]


def test_meta_only_on_final_answer_is_sql_null_elsewhere(test_db, monkeypatch):
    from sqlalchemy import text

    monkeypatch.setattr(agent, "run_turn", fake_turn("ok"))
    post("q")
    with test_db() as s:
        assert s.execute(text("select role from chats where meta is not null")).scalars().all() == ["assistant"]
        assert s.execute(text("select count(*) from chats where tool_calls is not null")).scalar() == 1


def test_cards_for_models_named_in_answer():
    cards = agent._cards_for("Try the GDS18V-800CPB15 (1450 ft-lbs) or the GBA18V40. gba18v40 again.", seen=set())
    assert [c["model_number"] for c in cards] == ["GDS18V-800CPB15", "GBA18V40"]


def test_reference_hint_lists_candidates_only_when_ambiguous():
    s = agent.Session([{"role": "user", "content": "lasers?"},
                       {"role": "assistant", "content": "Options: GLL269GC, GLL324GX and GLL81GX."}])
    hint = agent._reference_hint(s, "Where can I buy it?")
    assert hint and "GLL269GC, GLL324GX, GLL81GX" in hint["content"]
    assert agent._reference_hint(s, "Where can I buy the GLL81GX?") is None  # model named
    assert agent._reference_hint(s, "Show me green lasers") is None          # no pronoun
    assert agent._reference_hint(s, "Is this drill still available?") is None  # typed: may point further back
    assert agent._reference_hint(s, "How much is this one?") is not None
    assert agent._reference_hint(s, "Is this drill available? If not, what replaced it?") is None  # 'it' = the drill
    one = agent.Session([{"role": "assistant", "content": "The GLL269GC is $329."}])
    assert agent._reference_hint(one, "Where can I buy it?") is None         # single candidate
    msgs = [{"role": "system"}, {"role": "user"}]
    assert agent._with_hint(msgs, 2, hint)[-1] is hint and len(msgs) == 2  # request-only, history untouched
