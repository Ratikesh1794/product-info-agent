# Product Info Agent: Plan

Source: Yellow.ai take-home (email from Anirudh Shenoy, Mon 16 Nov 2026). Review call at 6 PM IST. They grade **depth and clarity of understanding** and how scenarios are handled, not polish.

## 1. Problem statement (verbatim from the email)

**Use case.** Bosch Power Tools wants to replace the basic chatbot on their website with an AI agent that helps visitors find information about Bosch products without having to navigate the site. Scope: power tools, measuring tools, hand tools, batteries and accessories across Bosch and sister brands (Dremel, RotoZip, CST/berger).

**Data.** `bosch_product_catalog_mock.csv`, mock data modelled on a real catalog: ~2,200 products, each with descriptions, feature lists, kit contents, pricing, status (active / discontinued / coming soon), compatibility info, retailers, and a `technical_specs` column holding category-specific specs as JSON. URLs in the CSV are fake, only representative.

**Build.** An agent that sits on the website and answers product questions using this catalog. It should handle:

1. "What's the difference between the GSR18V-535CN and the GSR18V-535CB25?" (compare)
2. "I need an 18V impact wrench with at least 500 ft-lbs of torque under $300." (spec and price filter)
3. "Which oscillating blades fit my StarlockPlus tool?" (compatibility)
4. "Is this drill still available? If not, what replaced it?" (status and replacement)
5. "Do you have a green-beam line laser with at least 100 ft range?" (spec search)
6. "Where can I buy it?" (follow-up, resolves "it" from context, retailers)
7. "Do you have the 18V heated jacket in a women's medium?" (variant and size check)

**Deliverables.**
- A working agent we can chat with (simple UI or CLI is fine).
- A few example conversations, **including ones where the agent says it doesn't know or asks a clarifying question**.

**Freedom.** Any framework, model or coding agent.

**Review focus.** Depth and clarity of understanding, and handling of different scenarios.

## 2. What the data actually looks like (probed)

| Fact | Consequence |
|---|---|
| 2,261 rows, 37 cols, no duplicate `model_number`, `msrp_usd` never empty | Model number is a safe exact-lookup key |
| Brand: Bosch 1995, Dremel 215, CST/berger 26, RotoZip 25 | Brand filter is cheap |
| Category: Accessories 1059, Power Tools 631, Measuring 166, Rotary Tool Acc. 130, Jobsite Apparel 83, Hand 70, Rotary 58, Digital Fab 27 | Apparel exists, so the jacket question is answerable |
| Status: Active 1969, **Discontinued 217**, Temp. Out of Stock 42, Coming Soon 33 | 4 statuses, not 3. "Temporarily Out of Stock" needs its own wording |
| `replacement_model` filled on 156 of 217 discontinued | **61 discontinued items have no replacement**, so the agent must say so and not invent one |
| `technical_specs` JSON has **175 distinct keys**, sparse per category | Cannot be a fixed schema. Needs a spec-key discovery step |
| Torque appears under several keys and units (`max_fastening_torque_ft_lbs`, `nut_busting_torque_ft_lbs`, `max_torque_in_lbs`) | "≥500 ft-lbs" needs unit normalisation, and the agent should state which torque it used |
| `compatible_with` is free text ("Bosch 12V Max"); `battery_platform` is a separate field | Compatibility needs a structured path (platform and shank or system tokens), not LLM guessing |
| `available_at` is a pipe-separated retailer list; URLs are fake | Answer with retailer names only. Never present `product_url` as real |
| `key_features`, `whats_in_the_box` are pipe-separated | Split on load |

Open data checks still to do: variants and sizes for the jacket (is size a separate SKU or only in the name?), the `Starlock`/`StarlockPlus` tokens, and the line-laser range key.

## 3. Design principles

1. **Structured facts come from code, not from the LLM.** The model decides *what to ask*. Deterministic tools return the rows. The model only phrases the answer from tool results.
2. **Never answer from memory.** Every product claim must trace to a tool result. If the tool returns nothing, the agent says it doesn't know.
3. **Ask when ambiguous, answer when not.** Clarify only if the choice changes the result (e.g. "which tool do you have?" for blade fit).
4. **Show the interpretation.** When normalising ("500 ft-lbs → 6000 in-lbs, using max fastening torque"), state it.
5. **Smallest thing that works.** Pandas/in-memory over a vector DB, because 2,261 rows fit in RAM.

## 4. HLD

```
┌────────────────────────────┐        ┌───────────────────────────────────────────┐
│ Frontend (React + TS)      │  HTTP  │ Backend (FastAPI)                         │
│  Chat UI                   │ ─────▶ │  POST /api/chat  (SSE stream)             │
│  - message list            │        │      │                                    │
│  - product cards           │ ◀───── │      ▼                                    │
│  - streamed tokens         │        │  Agent loop (LLM + tool-calling)          │
└────────────────────────────┘        │   system prompt: grounding + refusal rules│
                                      │      │  tool calls        ▲ tool results   │
                                      │      ▼                    │                │
                                      │  Catalog tools (deterministic)             │
                                      │   search_products   get_product            │
                                      │   compare_products  find_compatible        │
                                      │   check_availability describe_catalog      │
                                      │      │                                     │
                                      │      ▼                                     │
                                      │  CatalogStore (in-memory, loaded at start) │
                                      │   - typed Product models (Pydantic)        │
                                      │   - parsed specs + in/ft-lbs mirroring     │
                                      │   - model-number index + fuzzy suggest     │
                                      │   - session state (last product, filters)  │
                                      └──────────────────┬────────────────────────┘
                                                         ▼
                                            data/bosch_product_catalog_mock.csv
```

### Components

- **Frontend.** Single chat page, streams the reply. Renders product cards from structured `products` payloads (name, model, price, status badge, retailers) beside the text. Session id in memory.
- **`/api/chat`.** Takes `{session_id, message}`, returns an SSE stream of `token`, `products` and `done` events. Conversation history is held server-side per session (in-memory dict, enough for a demo).
- **Agent loop.** One LLM with tool calling (OpenAI SDK, no framework), max N tool iterations. The system prompt carries the rules: cite only tool results, say "I don't know" on empty results, ask a clarifying question when required inputs are missing, never invent a price, replacement or retailer.
- **Tools.** Each returns compact JSON capped at about 10 rows, so context stays small.
- **CatalogStore.** Built once at startup. Cleans types, splits pipe fields, parses `technical_specs` into a spec dict and a normalised numeric view (unit conversion), and indexes model numbers with punctuation stripped (`GSR18V-535CN` ≈ `gsr18v535cn`).

### Tool contracts

| Tool | Inputs | Handles question |
|---|---|---|
| `search_products` | query, category, subcategory, brand, voltage, price range, `compatible_with`, spec filters `[{key, op, value}]`, include_discontinued, sort | 2, 5, 7. Reports `missing_spec_data` and `discontinued_hidden` |
| `describe_catalog` | category / subcategory | Spec keys with examples, so the model filters on real keys |
| `get_product` | model_number or SKU | Details; `did_you_mean` on typos |
| `compare_products` | 2–4 model numbers | 1. Only differing fields plus the shared ones |
| `find_compatible` | tool model or system, accessory query | 3. Tier-aware whole-word match, surfaces data conflicts |
| `check_availability` | model_number | 4, 6. Status, replacement and how it differs, retailers, caveats |

Implemented in `backend/app/services/tools.py`, tested per scenario in `backend/tests/test_tools.py`. Each tool's Pydantic args model is both the OpenAI function schema and the validator. Invalid args come back as an error the model can correct.

Scenario 6 ("Where can I buy it?") needs a **resolved referent**. The agent loop keeps `last_products` in the session and passes it as context. If it's ambiguous (the last turn listed 5 products), it asks which one.

### Scenario handling matrix

| # | Query | Path | Edge cases the agent must handle |
|---|---|---|---|
| 1 | Compare two models | `get_product` ×2 → `compare_products` | Model not found → say so and offer the nearest match. One model discontinued → mention it |
| 2 | 18V impact wrench, ≥500 ft-lbs, <$300 | `describe_catalog` → `search_products` | Multiple torque keys: state which one. No match → say so and relax one constraint explicitly ("closest is 480 ft-lbs at $279") |
| 3 | Blades for StarlockPlus | `find_compatible` | Doesn't name a tool → ask. Starlock vs StarlockPlus vs StarlockMax are distinct, so don't conflate |
| 4 | Still available? replacement? | `check_availability` | Discontinued with no replacement → "no replacement on record". Also "Temporarily Out of Stock" and "Coming Soon" |
| 5 | Green-beam line laser ≥100 ft | `search_products` (category and spec filter) | Zero hits → don't fabricate, report the nearest and say what's missing |
| 6 | Where can I buy it? | session referent → `check_availability` | Ambiguous referent → clarify. Retailer names only (fake URLs) |
| 7 | 18V heated jacket, women's medium | `search_products` (apparel) | If size and stock aren't in the data, say the catalog doesn't track size or stock. Don't guess |

Cross-cutting: out-of-scope questions (non-Bosch, general advice) get a polite redirect. Prompt-injection text inside product descriptions is treated as data. Misspelled model numbers go through fuzzy matching.

## 5. Repo layout (already scaffolded)

```
backend/app/
  main.py                    app + CORS + router
  api/routes/{health,chat}.py
  core/config.py
  schemas/                   chat + product pydantic models
  services/
    catalog.py               load, clean, normalise, index
    tools.py                 tool functions + JSON schemas
    agent.py                 LLM loop, session state
backend/tests/               per-scenario tool tests + agent transcript tests
frontend/src/{api,components,hooks,types}
docs/PLAN.md   docs/conversations.md   (example transcripts)
```

## 6. Build order

1. **CatalogStore**: load CSV, clean, parse specs, unit-normalise, model-number index. Test with the 7 queries as plain function calls, no LLM.
2. **Tools** with unit tests for each scenario, including the "none found" paths.
3. **Agent loop** (non-streaming), CLI harness to iterate quickly. Tune the system prompt against the scenario matrix.
4. **`/api/chat` with SSE**, session store.
5. **Chat UI** with product cards.
6. **Example conversations** in `docs/conversations.md`: the 7 happy paths plus at least 4 where the agent declines or asks (discontinued with no replacement, impossible spec combo, ambiguous "it", out-of-scope, jacket size not tracked).
7. **Review prep**: one page on trade-offs (see below).

## 7. Decisions and trade-offs to be ready to defend

| Decision | Choice | Why / alternative |
|---|---|---|
| Retrieval | Structured filters and keyword and model-number index, no embeddings | Catalog is structured and small. Embeddings add cost and vague matches. Add a vector index only if free-text "vibe" queries become common |
| Framework | Raw OpenAI SDK tool loop | Fewer moving parts to explain. LangGraph or similar adds nothing for a single agent |
| Specs | Discover keys at runtime (`describe_catalog`) | 175 keys are too many for the prompt |
| Hallucination control | Answer only from tool output, empty result → "don't know" | Core requirement from the brief |
| State | In-memory sessions | Fine for a demo. Redis in production |
| Evals | Scripted scenario tests asserting the tool calls and key facts in the reply | Shows how we'd catch regressions |

## 8. Open questions

- LLM: OpenAI SDK, key in `backend/.env` (`OPENAI_API_KEY`), model set by `OPENAI_MODEL`.
- UI vs CLI: the email accepts either. Default is a minimal chat UI since the FE scaffold exists. A CLI harness is built anyway in step 3.
- Should the email thread get a clarifying question (jacket size data, stock levels)? Best decided after the data probe in step 1.
