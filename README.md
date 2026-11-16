# Product Info Agent

Chat agent that answers Bosch product questions from `backend/data/bosch_product_catalog_mock.csv`.
Design: `docs/PLAN.md` · Data findings: `docs/DATA.md` · Example conversations (generated): `docs/conversations.md`

## Backend (FastAPI, uv)

```
cd backend
cp .env.example .env                       # set OPENAI_API_KEY, DATABASE_URL
createdb product_agent                     # or: docker compose up -d (see docker-compose.yml)
uv run fastapi dev app/main.py             # API on :8000, POST /api/chat streams SSE
uv run python -m app.cli                   # chat in the terminal (shows tool calls)
uv run pytest -q                           # catalog, tools, API + Postgres (createdb product_agent_test)
uv run python -m evals.run --repeat 3      # live LLM evals, rewrites docs/conversations.md
```

Chat history lives in Postgres: `sessions` (one per conversation, scoped to an anonymous browser id) and
`chats` (every message in OpenAI format, so a conversation replays into the model after a restart).
The API applies Alembic migrations on startup; `uv run alembic upgrade head` does it by hand.

## Frontend (React + TS, Vite)

```
cd frontend && pnpm install && pnpm dev
```
