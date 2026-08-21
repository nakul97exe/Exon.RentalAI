# Exon Rental — Agentic RAG GIS Assistant

**Parcel-aware rental housing compliance assistant.**

Ask a natural-language question about a rental housing ordinance and get a grounded,
cited answer. Click a parcel on the map first, and the answer changes based on that
property's real attributes — because the rule that applies depends on how many units
the building has.

> Click a 30-unit building → **$13,000**.
> Click the single-family house next door → **one month's rent**.
> Same question. Different answer. Both correct. Both cited.

Built as a postgraduate AI/ML capstone. Demo city: Palo Alto, CA.

---

## Table of Contents

1. [The problem](#1-the-problem)
2. [What it does](#2-what-it-does)
3. [Why this is Agentic RAG, not plain RAG](#3-why-this-is-agentic-rag-not-plain-rag)
4. [Tech stack](#4-tech-stack)
5. [Folder structure](#5-folder-structure)
6. [File-by-file reference](#6-file-by-file-reference)
7. [Flow: document upload](#7-flow-document-upload)
8. [Flow: shapefile upload](#8-flow-shapefile-upload)
9. [Flow: asking a question](#9-flow-asking-a-question)
10. [The agents in detail](#10-the-agents-in-detail)
11. [Deployment](#11-deployment)
12. [Testing and results](#12-testing-and-results)
13. [Known limitations](#13-known-limitations)
14. [Future roadmap](#14-future-roadmap-parked)
15. [Assignment task mapping](#15-assignment-task-mapping)

---

## 1. The problem

A tenant facing eviction wants to know what they're owed. The answer lives in two
places that never talk to each other:

- **The ordinance** — a PDF of municipal code, written in legal prose
- **The property record** — a GIS parcel dataset with unit counts, zoning, land use

Neither alone answers the question. The ordinance says *"buildings with 10 or more
units pay $13,000 for a 2-bedroom."* It doesn't know how many units *this* building
has. The GIS layer knows the unit count but nothing about the law.

A generic document chatbot reads the PDF and stops there. It will happily quote you
a figure for a rule that doesn't apply to your building.

**This project joins the two.**

---

## 2. What it does

1. Upload a rental housing ordinance (PDF / TXT / CSV / Excel) → chunked, embedded,
   stored in a vector database
2. Upload a parcel shapefile (`.zip`) for any city → parsed in-browser, rendered on
   an Esri map
3. Click a parcel → it becomes the context for your question
4. Ask a question in plain English → a three-agent system plans, retrieves, reasons,
   generates, and verifies the answer

Every answer carries:
- **Source chips** — the exact ordinance sections used, with relevance scores
- **A verification badge** — whether every claim traces back to a source
- **A reasoning trace** — the plan, the tools chosen, the queries tried

---

## 3. Why this is Agentic RAG, not plain RAG

Plain RAG retrieves once and answers, regardless of whether what it retrieved was
any good. This system has three self-correcting behaviours:

| Behaviour | Where | What it does |
|---|---|---|
| **Tool selection** | Planner | Decides whether the question needs documents, parcel data, or both |
| **Query rewriting** | Planner | Rewrites casual phrasing into the ordinance's own wording |
| **Sufficiency check + retry** | Retriever-Reasoner | Judges its own retrieval and searches again with a refined query, up to 2 retries |
| **Claim verification** | Validator | Independently checks the answer against the sources and flags unsupported claims |

**A worked example of the loop firing.** Asked *"how much do I get if I'm kicked
out?"*, the planner rewrote the query to `relocation assistance eviction without
fault` — much closer to the document's own language. Asked *"what about the money?"*,
the reasoner judged the first retrieval insufficient, refined the query, searched
again, and then correctly asked the user which payment they meant rather than
guessing.

That's the difference: **the system evaluates its own work and acts on the result.**

---

## 4. Tech stack

### Backend

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI | Async-capable, auto-generated `/docs`, native file uploads |
| Document parsing | `PyPDFLoader`, `TextLoader`, pandas | Covers PDF, TXT, CSV, Excel |
| Chunking | Custom section-aware splitter + `RecursiveCharacterTextSplitter` | A legal section is a self-contained rule |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) | 384-dim, ~90MB, free, no API dependency |
| Vector store | Chroma (embedded, persisted to disk) | No server to run, no external service |
| LLM | OpenRouter → `anthropic/claude-sonnet-4.5` | One key, many models, easy to swap |
| Agents | Plain Python classes/functions | The reasoning steps stay visible and explainable |

### Frontend

| Layer | Choice |
|---|---|
| Framework | React 19 + Vite |
| Mapping | Esri ArcGIS JS SDK 4.31 (`@arcgis/core`) |
| Shapefile parsing | `shpjs` — runs entirely in the browser |
| Styling | Plain CSS with custom properties (dark theme) |

### Infrastructure

| Layer | Choice |
|---|---|
| Backend host | Azure App Service (Linux, Python 3.11) |
| Frontend host | Azure Static Web Apps |
| CI/CD | GitHub Actions — separate CI and deploy workflows |
| Auth to Azure | Publish profile (backend), deployment token (frontend) |

### Deliberate non-choices

- **No LangChain agent framework.** LangChain is used for loaders, splitters,
  embeddings, and the Chroma wrapper. The agent loop is hand-written so every
  reasoning step is inspectable — which is the thing being graded.
- **No external embedding API.** Embeddings run locally, so the only paid dependency
  is the chat LLM.
- **No database.** Chroma persists to disk; parcel attributes travel with each
  request and are never stored server-side.

---

## 5. Folder structure

```
paloAltoRentalGIS/
│
├── .github/workflows/
│   ├── ci.yml                     # verify: lint, compile, import, build
│   └── deploy.yml                 # ship: backend → App Service, frontend → SWA
│
├── backend/
│   ├── app/
│   │   ├── __init__.py            # sqlite3 shim for Azure Linux (load-bearing)
│   │   ├── main.py                # FastAPI app, CORS, router registration
│   │   ├── config.py              # env vars, paths, model names
│   │   ├── rag.py                 # plain-RAG baseline + shared prompt/context helpers
│   │   │
│   │   ├── routers/
│   │   │   ├── upload_document.py # POST /api/upload_document
│   │   │   └── query.py           # POST /api/query
│   │   │
│   │   ├── ingestion/
│   │   │   ├── document_loader.py # any file type → LangChain Documents
│   │   │   └── chunker.py         # section-aware chunking with size fallback
│   │   │
│   │   ├── vectorstore/
│   │   │   ├── embeddings.py      # cached sentence-transformers model
│   │   │   └── chroma_client.py   # add, search, stitch split sections
│   │   │
│   │   ├── parcel_data/
│   │   │   └── parcel_store.py    # cleans parcel attributes from the request
│   │   │
│   │   ├── agents/
│   │   │   ├── planner_agent.py            # which tools? rewrite the query
│   │   │   ├── retriever_reasoner_agent.py # call tools, judge, retry
│   │   │   ├── generator_agent.py          # write the grounded answer
│   │   │   ├── validator_agent.py          # verify claims against sources
│   │   │   ├── orchestrator.py             # sequence the four
│   │   │   └── json_utils.py               # shared LLM-JSON parser
│   │   │
│   │   └── llm/
│   │       └── openrouter_client.py        # plain requests.post to OpenRouter
│   │
│   ├── data/                      # gitignored — regenerated by uploads
│   │   ├── chroma_store/
│   │   └── uploaded_documents/
│   │
│   ├── scratch_*.py               # throwaway test scripts (gitignored)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   └── src/
│       ├── main.jsx               # entry; Esri assetsPath + dark theme
│       ├── App.jsx                # app shell, shared state
│       ├── index.css              # dark theme, layout, Esri overrides
│       │
│       ├── api/client.js          # fetch wrappers for both endpoints
│       ├── lib/shapefile.js       # zip → GeoJSONLayer, ID-field detection
│       │
│       └── components/
│           ├── TopBar.jsx         # title + counts
│           ├── IconRail.jsx       # 56px icon strip
│           ├── railItems.js       # single source of truth for rail/drawer labels
│           ├── Drawer.jsx         # 320px slide-out, routes to a panel
│           ├── MapView.jsx        # Esri map + click-to-select
│           ├── ChatPanel.jsx      # conversation, sources, badge, trace
│           ├── Footer.jsx         # legend + copyright
│           ├── Icon.jsx           # inline SVG icon set
│           └── panels/
│               ├── LayersPanel.jsx        # Esri LayerList
│               ├── AddDataPanel.jsx       # shapefile upload
│               ├── DocumentsPanel.jsx     # document upload
│               ├── FindParcelPanel.jsx    # Esri Search
│               └── BaseMapGalleryPanel.jsx
│
├── docs/
│   └── PROJECT_DOCUMENTATION.md   # this file
│
├── PROJECT_BRIEF.md               # original handoff brief
└── .gitignore
```

---

## 6. File-by-file reference

### Backend — entry and config

**`app/__init__.py`** — Runs before any submodule. Swaps `pysqlite3-binary` in as
`sqlite3` because Azure's Linux image ships a version older than Chroma's minimum
(3.35). Must stay the first thing imported. No-op locally.

**`app/main.py`** — Creates the FastAPI app, adds CORS middleware using origins from
config, registers routers, exposes `GET /health`.

**`app/config.py`** — Single place for paths and model names. Everything env-overridable
so Azure can set `DATA_DIR=/home/data` and `ALLOWED_ORIGINS` without a code change.

### Backend — ingestion

**`ingestion/document_loader.py`** — `load_documents(path)` dispatches on file
extension: PDF → `PyPDFLoader` (one Document per page), TXT/MD → `TextLoader`,
CSV/Excel → pandas, flattened to `col: value | col: value` lines so column names stay
attached to their values. Raises `UnsupportedFileType` or a clear error for scanned
PDFs with no text layer.

**`ingestion/chunker.py`** — Two-stage:

1. **Section split.** Joins pages back together (a section can straddle a page break),
   finds headings by regex, cuts from each heading to the next. Every section number
   appears **twice** in these documents — once in the table of contents, once as the
   real heading — so keeping the *last* match per number discards the TOC copy.
2. **Size enforcement.** `all-MiniLM-L6-v2` silently truncates past ~256 tokens
   (~1000 chars), so oversized sections are sub-split with
   `RecursiveCharacterTextSplitter`. Each piece keeps its `section` metadata plus
   `part`/`parts`.

Falls back to plain size-based chunking for documents with no recognisable section
numbering, so any PDF still works.

### Backend — vector store

**`vectorstore/embeddings.py`** — `get_embeddings()` wrapped in `@lru_cache(maxsize=1)`
so the model loads once. `normalize_embeddings=True` so cosine similarity isn't
skewed by chunk length.

**`vectorstore/chroma_client.py`** — Four things worth knowing:

- **`_chunk_id`** builds a stable ID from `source_file::section::part`, so re-uploading
  the same document **overwrites** instead of duplicating every chunk.
- **`search`** — raw similarity search.
- **`get_full_section`** — reassembles a section from its parts, ordered by `part`.
- **`search_sections`** — over-fetches `k*4` chunks, dedups by section, and stitches
  split sections back together. **This matters:** section 9.68.060 splits into 7
  parts, so a naive search can return the dollar table without the exemption that
  says the section only applies to 10+ unit buildings. Rejoining guarantees the rule
  and its exceptions arrive together.

### Backend — parcel data

**`parcel_data/parcel_store.py`** — `get_parcel_attributes(apn, raw)` cleans what the
frontend sent: keeps the documented useful fields in a stable order, drops geometry
(thousands of characters of coordinates, useless to an LLM), drops empty values, and
falls back to any other short fields for cities with different column names.

**Nothing is stored server-side.** Attributes travel with each request, so two
concurrent users can never see each other's parcel.

### Backend — LLM

**`llm/openrouter_client.py`** — `chat(messages, model, temperature, max_tokens)`.
A plain `requests.post` to OpenRouter's chat-completions endpoint. Raises `LLMError`
for network failures, non-200 responses, and unexpected response shapes.
`temperature=0` by default — grounded legal answers should be repeatable.

### Backend — RAG helpers

**`rag.py`** — Holds `SYSTEM_PROMPT` (the five grounding rules), `MIN_SCORE = 0.15`,
`build_context()`, and `answer_question()`.

`answer_question` is the **plain-RAG baseline** — retrieve once, answer, done. The
agent path doesn't call it, but it's kept deliberately: it lets you run the same
question through both paths and show the difference.

### Backend — agents

See [section 10](#10-the-agents-in-detail).

### Backend — routers

**`routers/upload_document.py`** — `POST /api/upload_document`. Sanitises the filename
with `Path(...).name` (client-supplied paths could otherwise escape the upload
directory), validates the extension **before** writing, runs load → chunk → store,
deletes the file if ingestion fails, returns `{filename, pages, chunks, sections}`.

Deliberately a **sync `def`**: parsing and embedding are CPU-bound with nothing to
await, so FastAPI runs it in a threadpool and the event loop stays free.

**`routers/query.py`** — `POST /api/query`. Pydantic body of `question`, `apn`,
`parcel_attributes`. Maps exceptions to status codes: `PlanAgentError` → 400,
`LLMError` → 502 (upstream problem, not ours), anything else → 500.

### Frontend

**`main.jsx`** — Sets `esriConfig.assetsPath` to Esri's CDN. Without this, icons and
fonts 404 — Vite can't see runtime-constructed asset URLs, so it never bundles them.

**`App.jsx`** — Owns three pieces of state: `activePanel` (which drawer), `view` (the
Esri MapView, lifted so drawer widgets can use it), `selectedParcel` (`{apn, attributes}`).

**`lib/shapefile.js`** — `layersFromShapefileZip(file)` unzips with `shpjs` (which
reads the `.prj` and reprojects to WGS84), builds a `GeoJSONLayer` from a Blob URL,
and applies renderers: polygons transparent with a purple outline, points blue.
`detectIdField()` finds the parcel identifier column — `APN`, `PARCELID`, `PIN`, `AIN`
— shared with the map click handler so both use one pattern.

**`components/MapView.jsx`** — Creates the map in a `useEffect` with `[]`, returns
`view.destroy()` for cleanup (StrictMode double-mounts, and without cleanup you leak
a second map). Callbacks are held in refs updated inside an effect, so a changing
callback identity never tears down the map. `view.on("click")` → `hitTest` → attributes
→ `onParcelSelect`.

**`components/ChatPanel.jsx`** — Conversation state, source chips, validation badge,
and a collapsible reasoning trace.

**Esri widgets in React** — `LayersPanel`, `BaseMapGalleryPanel`, `FindParcelPanel`,
and `Footer` all mount real Esri widgets into the app's own DOM via the widget
`container` property. Each creates a **throwaway inner div** first, because Esri's
`destroy()` removes its container element from the DOM — hand it the React-owned div
and React's node disappears, leaving the widget rendering into a detached element.

---

## 7. Flow: document upload

```
User picks a PDF in the Documents drawer
   │
   ▼  DocumentsPanel.jsx → api/client.js
POST /api/upload_document   (multipart/form-data, field name "file")
   │
   ▼  routers/upload_document.py
1. Sanitise filename (Path(...).name — blocks path traversal)
2. Validate extension BEFORE writing to disk
3. Write to data/uploaded_documents/
   │
   ▼  ingestion/document_loader.py
4. PDF → PyPDFLoader → one Document per page
   │
   ▼  ingestion/chunker.py
5. Join pages into one string
6. Find section headings, drop the table-of-contents copies
7. Cut heading-to-heading  →  9 sections
8. Sub-split anything over 1000 chars  →  37 chunks
   │
   ▼  vectorstore/chroma_client.py
9. Build stable IDs (source::section::part)
10. Chroma embeds each chunk (384 numbers) and persists
   │
   ▼
{"filename": "...", "pages": 7, "chunks": 37, "sections": [9 numbers]}
```

**No LLM is involved.** Chunking a PDF has one correct answer; there's nothing to
reason about. Agents appear only at query time.

---

## 8. Flow: shapefile upload

Entirely client-side — the backend never sees the shapefile.

```
User picks parcels.zip in the Add data drawer
   │
   ▼  lib/shapefile.js
1. shpjs unzips, reads .shp/.dbf/.prj, reprojects to WGS84
2. Filter to supported geometry types
3. Read the geometry type off the first feature
   (the shapefile format allows only one type per file)
4. Wrap features in a Blob URL → new GeoJSONLayer
5. Attach renderer + popup template with explicit fieldInfos
   │
   ▼  AddDataPanel.jsx
6. view.map.add(layer); await layer.when()
7. Zoom to layer.fullExtent
8. Report feature count up to App → TopBar
```

**Why client-side:** the map needs the geometry anyway, so parsing in the browser
avoids uploading 20MB and re-serving it. The trade-off is that the backend has no
parcel database — which is exactly why attributes travel with each query.

---

## 9. Flow: asking a question

```
User clicks parcel 127-53-008, types a question
   │
   ▼  MapView.jsx
view.on("click") → hitTest → { apn: "127-53-008", attributes: {...} }
   │
   ▼  App.jsx → ChatPanel.jsx → api/client.js
POST /api/query { question, apn, parcel_attributes }
   │
   ▼  routers/query.py → agents/orchestrator.py
   │
   ├── 1. PLANNER  ─────────────────────────── LLM call #1
   │      in:  question, has_apn, parcel field NAMES (not values)
   │      out: { needs_documents, needs_parcel, search_query, reasoning }
   │
   ├── 2. RETRIEVER-REASONER
   │      ├─ get_parcel_attributes(apn, raw)   ← once, outside the loop
   │      └─ loop, max 3 attempts:
   │           ├─ search_sections(query)        ← local embeddings, no API
   │           ├─ filter score > MIN_SCORE
   │           ├─ summarise findings (labels only — cheap)
   │           ├─ check_sufficiency(...)        ── LLM call #2
   │           └─ sufficient? break : query = better_query
   │
   ├── 3. GENERATOR ─────────────────────────── LLM call #3
   │      in:  question, full section text, parcel attributes
   │      out: grounded answer with citations
   │
   └── 4. VALIDATOR ─────────────────────────── LLM call #4
          in:  answer + the same sources the generator saw
          out: { supported, unsupported_claims }
   │
   ▼
{ answer, sources[], parcel, validation{}, trace{} }
   │
   ▼  ChatPanel.jsx
Answer text · source chips · ✓ verified badge · collapsible trace
```

**Four LLM calls per question**, ~6–10 seconds. Plain RAG would be one call and
~2 seconds — that's the cost of the self-checking behaviour.

---

## 10. The agents in detail

### Planner — `planner_agent.py`

**Job:** decide what's needed. It never answers the question.

**Why it needs no documents:** it's classifying, not answering. Recognising that
*"kicked out"* means eviction, and that eviction rules depend on unit count, takes
language understanding — not facts.

**Two outputs that matter:**
- `needs_documents` / `needs_parcel` — which tools to run
- `search_query` — the question rewritten in the ordinance's wording. *"How much do
  I get if I'm kicked out?"* → `relocation assistance eviction without fault`

**Design details:**
- Receives parcel **field names**, not values — enough to know what's available,
  without spending tokens or being swayed by them
- `needs_parcel` is ANDed with `has_apn` in code, so the model can't plan a lookup
  that cannot succeed
- On malformed JSON it **falls back** to "use both tools" rather than raising — a
  formatting hiccup shouldn't kill the request

### Retriever-Reasoner — `retriever_reasoner_agent.py`

**Job:** call the tools, judge whether the results are enough, retry if not.

**The loop:**
```
query = plan.search_query
parcel = get_parcel_attributes(...)          ← once; a dict lookup can't change
for attempt in 1..3:
    documents = search_sections(query), filtered by MIN_SCORE
    verdict = check_sufficiency(question, summary_of_findings)
    if verdict.sufficient: break
    if not verdict.better_query or already tried it: break
    query = verdict.better_query
```

**Design details:**
- The sufficiency summary sends **section labels only**, not full text. It runs up to
  3 times; full sections would be ~24,000 characters of tokens for repeated yes/no
  questions.
- Absence is stated explicitly (`"Document sections found: none"`). Omitting the line
  entirely lets the model assume everything was fine, and the retry never fires.
- The check **fails open** — a broken LLM call reports "sufficient" so the loop stops,
  rather than burning all three attempts.
- The prompt explicitly says a missing user-supplied detail (bedroom count) is **not**
  a retrieval failure, otherwise it loops searching for data that doesn't exist.
- Duplicate-query guard: if the model suggests something already tried, stop.

### Generator — `generator_agent.py`

**Job:** write the answer. Receives documents; never searches.

**Prompt rules that do the work:**
1. Quote dollar amounts **verbatim**; never calculate one
2. Use parcel attributes to decide **which** rule applies, and say the deciding fact
   out loud
3. Include payment timing and splits when the section states them
4. The **only** permitted arithmetic is halving a stated total, because the ordinance
   itself describes that split
5. If a needed fact is missing, ask for it rather than assuming

`_format_parcel(None)` writes *"no parcel selected"* explicitly — without it the model
quietly invents a unit count.

A `strict` flag appends a tighter instruction, reserved for a validator-triggered
rewrite.

### Validator — `validator_agent.py`

**Job:** independently check the answer against the sources.

**Why a separate call:** ask a model whether its own answer was grounded and it says
yes. The validator gets a clean context — the answer text and the sources, no memory
of writing it, and a prompt whose only job is finding gaps.

**Design details:**
- Sees the **full section text**, unlike the reasoner's labels — the question here is
  "does this figure appear?", which a title can't answer
- Scores are omitted so it doesn't favour the top hit
- Parcel attributes are included and labelled as real data, or it flags *"this parcel
  has 30 units"* as unsupported
- Fails **open** with `checked: false`, and the UI shows no badge at all in that case
  — never a green tick you can't back up
- If the model returns `supported: true` but also lists claims, the **list wins**

**It works.** Running the same question on a weaker model produced *"for a total of
$16,000"* — a figure that appears nowhere in the ordinance, arrived at by adding
$13,000 + $3,000. The validator flagged it.

### Orchestrator — `orchestrator.py`

Sequences the four and assembles the response. No logic of its own — it owns the
request data and hands each agent only what that agent needs.

---

## 11. Deployment

```
git push to main
   │
   ├── ci.yml
   │     ├─ backend-check:  compileall → pip install → import smoke test
   │     └─ frontend-build: npm ci → lint → build
   │
   └── deploy.yml
         ├─ deploy-backend:  zip backend/ → Azure App Service (publish profile)
         └─ deploy-frontend: npm build with VITE_API_BASE → Azure Static Web Apps
              (needs: deploy-backend)
```

### Why two workflows

CI answers *"does the code work?"* and runs on every push and PR. Deploy answers
*"ship it"* and runs only on `main`. A CI failure means broken code; a deploy failure
means production may be half-updated. Different problems, different urgency.

### Key configuration

**Startup command:**
```
gunicorn -w 1 -k uvicorn.workers.UvicornWorker --timeout 600 --bind 0.0.0.0:8000 app.main:app
```

| Flag | Why |
|---|---|
| `-w 1` | Each worker loads its own copy of the embedding model — memory scales linearly with worker count |
| `-k uvicorn.workers.UvicornWorker` | FastAPI is ASGI; gunicorn speaks WSGI by default |
| `--timeout 600` | PyTorch import takes ~51s; the default 30s kills the worker mid-import and loops forever |

**App settings:**

| Setting | Purpose |
|---|---|
| `SCM_DO_BUILD_DURING_DEPLOYMENT=1` | Azure runs `pip install` on the instance, so wheels match the server platform and the upload stays ~200KB |
| `DATA_DIR=/home/data` | Only `/home` survives a restart on App Service Linux |
| `HF_HOME=/home/.cache/huggingface` | Caches the embedding model so it downloads once, not per cold start |
| `ALLOWED_ORIGINS` | The deployed frontend's URL — hardcoded localhost would block every real request |
| `WEBSITES_CONTAINER_START_TIME_LIMIT=1800` | The default 230s is shorter than a cold PyTorch start |

### Three deployment problems worth recording

1. **sqlite3 too old.** Azure's Linux image ships sqlite3 < 3.35; Chroma raises a
   `RuntimeError` at import. Fixed with `pysqlite3-binary` (Linux-only marker — there
   are no Windows wheels) plus a `sys.modules` swap in `app/__init__.py`. A pure
   *system-library* mismatch — invisible locally, since Python bundles a newer sqlite3
   on Windows.

2. **CUDA PyTorch.** The default PyPI `torch` wheel bundles CUDA (~2.5GB) for a GPU
   App Service doesn't have. Pinning `torch==2.13.0+cpu` from PyTorch's own index
   cuts it to ~200MB.

3. **Green ≠ running.** `azure/webapps-deploy` uploads and finishes; Azure installs
   and starts afterwards. A green pipeline with a 503 site is expected, not a
   contradiction. Verification means hitting `/health`, not reading the pipeline.

### Known pipeline weakness

`ci.yml` and `deploy.yml` both trigger on push to `main` and run **concurrently**, so
a deploy can proceed even if CI fails. In a team the fix is requiring CI as a PR
status check so `main` is verified before merge; for direct pushes it'd be one
workflow with `needs:`.

---

## 12. Testing and results

### The primary test case

**Setup:** APN `127-53-008` (30 units), question: *"If a tenant with a 2-bedroom unit
here is evicted without fault, how much relocation assistance is owed?"*

**Result:**
> Based on the parcel data showing **30 units**, Section 9.68.060 applies rather than
> Section 9.68.050, because this section governs structures with 10 or more residential
> rental units. For a 2-bedroom unit, relocation assistance is **$13,000**. This amount
> is paid in two instalments: one half ($6,500) at notice, the remainder ($6,500) when
> the renter vacates. If occupied by a low-income household, a renter 60 or older, a
> disabled renter, or a minor, an **additional $3,000** applies.

Every figure verbatim from the ordinance. The section choice driven by real GIS data.
`✓ verified`.

### The inverse case

Clicking a **single-family** parcel and asking the same question returns Section
9.68.050 — one month's rent — *because* the parcel is under the 10-unit threshold.

**These two together are the proof.** Same question, different parcel, different
legally-correct answer.

### Guardrails

| Question | Result |
|---|---|
| "How many parking spaces are required per unit?" | Refused — not in the excerpts, no invented number |
| "What's the rent control limit in San Francisco?" | Refused — outside the uploaded document |
| "what about the money?" | Retry loop fired, then asked which payment was meant |
| No parcel selected + threshold question | Asked for the unit count rather than assuming |

### Model choice mattered

Running the primary test on `claude-3-haiku` produced the right dollar figure but
broke three prompt rules: never mentioned the unit count, omitted the payment split,
and computed a `$16,000` total. Switching to `claude-sonnet-4.5` fixed all three
**with no prompt change**.

**Lesson worth recording:** when a grounded-generation system breaks rules, check the
model tier before rewriting prompts. The generator prompt carries ~10 simultaneous
constraints, which is past what a small model reliably holds.

### Generalisation testing

Two other cities' ordinances were run through the ingestion pipeline:

| City | Section format | Result |
|---|---|---|
| Palo Alto | `9.68.060   Purpose.` | ✅ 9 sections, 37 chunks |
| San Joaquin | `§ 150.060  APPLICABILITY.` | ✅ 6 sections, 12 chunks |
| Los Angeles | `SEC. 45.83. RENTAL HOUSING.` | ❌ no match → size-based fallback |

The San Joaquin case only worked because the regex was broadened to accept `§`
prefixes and two-part numbers. **Los Angeles still fails** — uppercase `SEC.` and a
period-then-single-space after the number.

This is documented rather than hidden because it identifies the exact next feature
(see roadmap).

San Joaquin also revealed something more interesting: its ordinance is *Rental Housing
Standards* — habitability and inspection, **no dollar amounts and no unit thresholds**.
The two-tool architecture pays off specifically for ordinances with
**property-dependent thresholds**. That's a finding about where the design applies,
not a bug.

---

## 13. Known limitations

**Data and coverage**
- Parcel datasets have no occupancy status, rent registry status, inspection history,
  or bedroom count — these are internal housing-department records, absent from every
  public GIS dataset. Bedroom count must come from the user's question.
- Validated on one city end to end. Architecturally city-agnostic, empirically proven
  on Palo Alto.
- Section chunking assumes numbered sections. Documents that number differently fall
  back to size-based chunking, which works but loses the guarantee that a rule stays
  with its exemptions.

**Retrieval**
- No re-ranking model — raw embedding similarity only.
- All documents share one Chroma collection, and `/query` exposes no per-document
  filter. Indexing two cities at once can mix sources in one answer. The metadata and
  the filter parameter both exist; only the plumbing is missing.

**Reliability**
- Sufficiency and validation are themselves LLM calls, so they inherit the base model's
  reliability. Mitigation, not a guarantee.
- Four LLM calls per question → ~6–10s latency.

**Operations**
- No authentication or multi-user document isolation. Acceptable for a demo.
- Uploaded documents and the vector store live on App Service's `/home`; a redeploy may
  clear them, requiring re-upload.
- On the free App Service tier the app sleeps when idle, so the first request after a
  pause pays the full model-load cold start.

**Product**
- Answers are informational, not legal advice. A production version needs prominent
  disclaimers and a link to the city's own code.
- Ordinances are amended regularly; a stale index can be confidently wrong. Answers
  should carry a "last indexed" date.

**Frontend**
- The Find-parcel widget uses Esri's address geocoder, so it searches addresses, not
  APNs. Making it search by parcel ID needs a layer source built from the detected ID
  field.

---

## 14. Future roadmap (parked)

The idea: **any city, not just Palo Alto.** Upload an ordinance and a parcel layer,
and it works. The obstacles below are recorded from actual testing, not speculation.

### Next three features, in priority order

**1. Structure-inference agent** *(highest value)*

Replace hardcoded chunking regexes with an LLM call that reads the first 2–3 pages and
returns the document's own structure:

```json
{
  "has_sections": true,
  "heading_example": "SEC. 45.83. RENTAL HOUSING.",
  "regex": "^SEC\\.\\s+(\\d+\\.\\d+)\\.\\s+(.+)$",
  "citation_prefix": "LAMC"
}
```

One call per document, run once at upload. Fixes the Los Angeles failure **and** the
hardcoded `PAMC` citation prefix in the same step.

**2. Per-document filtering in `/query`**

`search_sections` already accepts a `source_file` filter and every chunk carries the
metadata. Exposing it through the API and adding a document picker makes multi-city
correct rather than merely possible.

**3. Parcel schema-mapping agent**

Show the LLM the shapefile's column names and one sample row; ask which field is the
parcel ID, the unit count, the zoning. Any county's schema then works, replacing the
current `APN|PARCELID|PIN|AIN` pattern.

### What genuinely blocks nationwide scale

| Obstacle | Nature |
|---|---|
| **Document acquisition** | ~19,000 US municipalities; codes sit behind Municode, American Legal Publishing, eCode360, each with its own terms. A licensing and data problem, not an AI one. |
| **Parcel data** | County-level, ~3,000 counties, inconsistent schemas, some paid. No free current national dataset. |
| **Applicability** | Only ~200 US cities have rent stabilisation, mostly CA/NY/NJ/OR/MD. Habitability codes are universal but rarely threshold-driven, so the GIS join matters less there. |
| **Freshness** | Ordinances amend continuously; a stale index is confidently wrong. |
| **Liability** | Telling a tenant they're owed $13,000 approaches legal advice. Shapes the product, not a blocker. |

### The defensible claim

Not "RAG over PDFs" — that's commodity. The differentiator is **joining unstructured
legal text to structured property data so the answer depends on the specific parcel.**

---

## 15. Assignment task mapping

| # | Requirement | Where |
|---|---|---|
| 1 | Project foundation | Repo, `.env.example`, `config.py`, layered structure |
| 2 | User interaction layer | React shell — upload panels, map, chat |
| 3 | Document ingestion (PDF/TXT/CSV/Excel) | `ingestion/document_loader.py` |
| 4 | Data prepared for semantic search | `ingestion/chunker.py` — section-aware + size fallback |
| 5 | Vector-based knowledge store | `vectorstore/embeddings.py`, `chroma_client.py` |
| 6 | Intelligent document retrieval | `search_sections` — over-fetch, dedup, section stitching |
| 7 | RAG pipeline | `rag.py` (baseline) and `generator_agent.py` (agent path) |
| 8 | Agent-based reasoning **using available tools** | Four agents; two heterogeneous tools — vector search and parcel lookup |
| 9 | Reliability and safety controls | Validator, score floor, retry caps, fail-open judgment calls, input validation, path-traversal guard, typed HTTP errors |
| 10 | Deploy and document | Azure App Service + Static Web Apps, GitHub Actions, this document |

**On task 8 specifically:** the assignment says agents use "available tools" — plural,
open-ended. The GIS parcel tool is one tool alongside document search. Document upload
and Q&A work independently: with no map interaction at all, the system still satisfies
tasks 1–10 from document Q&A alone. The GIS integration is **additive**.

---

## Running locally

```bash
# Backend
cd backend
python -m venv ../venv && ../venv/Scripts/activate    # Windows
pip install -r requirements.txt
cp .env.example .env                                   # add your OpenRouter key
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, upload an ordinance PDF, upload a parcel shapefile zip,
click a parcel, ask a question.

---

*Exon Rental — parcel-aware housing compliance.*
