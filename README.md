# Product Info Agent

An AI assistant for a power-tools website that answers product questions (specs, prices, compatibility,
availability, replacements and where to buy) from the Bosch / Dremel / RotoZip / CST/berger catalog in
`backend/data/bosch_product_catalog_mock.csv` (2,261 products).

Every product fact in an answer comes from a deterministic catalog lookup, never from the model's own knowledge.
When the catalog doesn't have the answer the agent says so, and when a question is ambiguous it asks.

## Features

**Agent**
- OpenAI tool-calling loop (`gpt-4.1` by default) over six typed catalog tools: search with spec filters,
  product details, side-by-side comparison, availability and replacements, accessory compatibility, and spec
  discovery
- Handles the catalog's traps: two torque specs on impact wrenches, laser working range vs range with receiver,
  three Starlock tiers, replacements that change platform (e.g. 12V to 18V), discontinued items with no
  replacement, stale "Coming Soon" dates. See `docs/DATA.md`
- Guards against silent failures: bad tool arguments return actionable errors, zero-result searches explain
  which filter excluded everything, truncated results include facets across all matches
- Resolves "it" / "this drill" safely: it asks or answers for each candidate instead of guessing

**App**
- Streaming chat (SSE) with product cards, status pills and a collapsible "Based on N catalog lookups" panel
  showing the exact filters used
- Product detail modal: specs table, features, box contents, compatibility, retailers and clickable
  replacement links, served by `GET /api/products/{model}`
- Conversation history in Postgres with a sidebar; each browser sees only its own conversations
- URL routing: `/c/<id>` for a conversation, `?product=<model>` for an open product. Both can be shared and
  reloaded, and back/forward work

**Quality**
- 38 backend tests (catalog, tools, API, real Postgres)
- Live eval harness: 17 scenarios against the real model, repeatable for flakiness, writes
  `docs/conversations.md`

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 0.5+ | Python backend (installs Python 3.12+ itself) |
| [pnpm](https://pnpm.io/) | 10+ | Frontend (Node 20+) |
| PostgreSQL | 15+ | Chat history (local install, or the included `docker-compose.yml`) |
| OpenAI API key | | The agent |

## Setup

### 1. Database

Local Postgres (e.g. Homebrew):

```bash
createdb product_agent
createdb product_agent_test        # only needed for the test suite
```

Or with Docker:

```bash
docker compose up -d               # Postgres 16 on :5432, user/password postgres/postgres
```

### 2. Backend

```bash
cd backend
uv sync
cp .env.example .env
```

Edit `backend/.env`:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1
DATABASE_URL=postgresql+psycopg://localhost:5432/product_agent
# with docker compose: postgresql+psycopg://postgres:postgres@localhost:5432/product_agent
```

Tables are created by Alembic migrations, which the API runs automatically on startup. To run them by hand:
`uv run alembic upgrade head`.

### 3. Frontend

```bash
cd frontend
pnpm install
```

No `.env` is needed in development: the Vite dev server proxies `/api` to `http://localhost:8000`.

## Run

Two terminals:

```bash
# backend: API on http://localhost:8000
cd backend && uv run uvicorn app.main:app --reload --port 8000

# frontend: app on http://localhost:5173
cd frontend && pnpm dev
```

Open http://localhost:5173.

**Terminal-only chat** (no database or frontend needed; shows every tool call):

```bash
cd backend
uv run python -m app.cli                                  # interactive
uv run python -m app.cli "Is the GSB12V-535B2 still available?" "Where can I buy it?"   # scripted turns
```

**PyCharm:** run configurations live in `.idea/runConfigurations` (local only, not committed). **Full stack**
starts the backend under the debugger plus `pnpm dev`; **Backend API**, **Backend CLI chat**, **Backend tests**
and **Backend evals** run individually.

## Test

```bash
cd backend
uv run pytest -q                                # 38 tests; Postgres tests skip if product_agent_test is unreachable
uv run python -m evals.run                      # 17 live scenarios against the real model
uv run python -m evals.run --repeat 3           # flakiness check: pass rate per scenario
uv run python -m evals.run --only q2 e8         # selected scenarios
uv run ruff check app tests evals

cd ../frontend
pnpm build && pnpm lint
```

The eval run rewrites `docs/conversations.md` with every transcript and exits non-zero on failure, so it can gate CI.
Use `TEST_DATABASE_URL` to point the tests at a different database.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Send a message, stream the answer as SSE: `token`, `tool_call`, `tool_result`, `products`, `error`, `done` |
| `GET` | `/api/sessions` | The browser's conversations, newest first |
| `GET` | `/api/sessions/{id}` | One conversation with its messages, cards and lookups |
| `DELETE` | `/api/sessions/{id}` | Delete a conversation |
| `GET` | `/api/products/{model}` | Full product detail for the modal |
| `GET` | `/api/health` | Liveness |

Chat and session endpoints require an `X-Client-Id` header (an anonymous id the frontend keeps in
`localStorage`). Interactive docs are at http://localhost:8000/docs.

## Project structure

```
backend/
  app/
    main.py              app factory: middleware + one router
    api/router.py        mounts every route module under /api
    api/routes/          chat (SSE), sessions, products, health
    core/                settings (.env), lifespan (catalog load + migrations)
    db/                  SQLAlchemy Base, models (sessions, chats), engine
    schemas/             request/response models
    services/
      catalog.py         load, clean and index the CSV in memory
      tools.py           the six agent tools (Pydantic args = OpenAI schemas)
      agent.py           system prompt + streaming tool-calling loop
      history.py         conversation persistence
    cli.py               terminal chat
  evals/run.py           live eval scenarios
  migrations/            Alembic
  tests/
frontend/
  src/
    main.tsx             routes: /, /c/:sessionId
    App.tsx              layout, URL ↔ conversation/product sync
    api/chat.ts          SSE client, sessions, products
    hooks/               useChat, useSessions
    components/          chat messages, product cards, product modal, sidebar, composer
docs/
  PLAN.md                problem statement, HLD, design decisions
  DATA.md                what the catalog contains and its traps
  GROUND_TRUTH.md        assignment questions answered straight from the CSV
  conversations.md       generated example conversations (from the evals)
```

## Design notes

- **No vector database or RAG pipeline.** The catalog is 2,261 structured rows, small enough to filter in memory.
  Exact filters beat embeddings for questions like "≥500 ft-lbs under $300". Postgres stores conversations, not the catalog.
- **No agent framework.** A plain OpenAI SDK loop is easier to reason about and debug.
- **Code owns state, the model owns language.** Facts, candidate products for "it", status counts and replacement
  differences are computed in code and handed to the model.

More in `docs/PLAN.md`.
