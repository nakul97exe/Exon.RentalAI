# Agentic RAG GIS Capstone — Project Brief

> **Purpose of this file:** This is a complete handoff document. Any developer or AI
> assistant picking this up should be able to start coding immediately without needing
> prior conversation context. It captures the assignment requirements, the architecture
> decided on, the real data available, and the exact build order.

---

## 1. Assignment Requirements (source of truth)

This is a postgraduate AI/ML capstone. The original assignment text:

> Build a Generative AI–powered application that enables users to query enterprise
> documents using autonomous AI agents. Uses LLMs, RAG, and Agentic AI to retrieve
> relevant information, reason over it, and generate accurate, context-aware responses.
> Users upload documents (PDF, TXT, CSV, Excel) and ask natural language questions.
> AI agents plan, retrieve, reason, and validate the final output.

### The 10 required tasks

1. Set up project foundation (repo, env config, structure)
2. Design user interaction layer (upload docs + ask questions)
3. Implement document ingestion (PDF/TXT/CSV/Excel)
4. Prepare data for semantic search (chunking)
5. Build vector-based knowledge store (embeddings + vector DB)
6. Implement intelligent document retrieval (similarity search)
7. Develop RAG pipeline (retrieved context + LLM → grounded answer)
8. Implement agent-based reasoning (agents that plan, retrieve, reason, generate,
   **using available tools** — this phrase is why adding a GIS tool is fully compliant)
9. Add reliability and safety controls (guardrails, error handling)
10. Deploy and document (architecture, workflow, limitations)

**Deadline constraint:** ~3 weeks total, alongside an active job search. Scope must
stay small and finishable, not exhaustive.

### Why GIS is included and does not violate the assignment

Task 8 explicitly says agents use "available tools" (plural, open-ended). A parcel-data
lookup tool is just one more tool alongside the document vector-search tool. Document
upload (tasks 2/3) is still fully implemented and independently usable — GIS is
**additive**, not a replacement. If a user never touches the map, the app still
satisfies all 10 base tasks purely from document Q&A.

**Non-negotiable:** the document upload flow must remain real and functional on its own,
not decorative, or task 2/3 compliance is at risk.

---

## 2. Concept: Rental Housing Compliance / Rights Assistant

A user can:
1. Upload a parcel shapefile/CSV for **any city** (not hardcoded) → parcels render on
   an Esri map.
2. Upload a housing/rental ordinance document (PDF/TXT/CSV/Excel) → gets ingested into
   a vector store.
3. Search for a parcel by APN, or click it directly on the map, to select it as context.
4. Ask a natural-language question in a chat panel. A 3-agent system answers using
   **both** the uploaded document (via RAG) and the selected parcel's real attributes
   (via a GIS tool), citing sources.

This is intentionally **generalizable** — not hardcoded to one city. Palo Alto is the
demo/test city because we have real data for it (see Section 4), but the architecture
must not assume Palo Alto-specific fields beyond what's documented below.

---

## 3. Architecture & Flow

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (React + Esri ArcGIS JS SDK)                      │
│                                                               │
│  Map (default: California) ──upload shapefile──> parcels    │
│                                                    render     │
│  Upload panel ──upload PDF/TXT/CSV/Excel──> sent to backend  │
│  APN search box ──> highlights + selects parcel on map       │
│  Click parcel on map ──> also selects it                     │
│  Chat panel ──{question, selected_apn}──> POST /query        │
└───────────────────────────┬───────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI)                                           │
│                                                               │
│  POST /upload/shapefile  → parse geometry+attrs → store      │
│  POST /upload/document   → ingest → chunk → embed → Chroma   │
│  GET  /parcel/search?apn= → lookup in parcel table            │
│  POST /query {question, apn} → AGENT ORCHESTRATION:           │
│                                                               │
│     PLANNER AGENT                                             │
│       → decides: need document lookup? parcel lookup? both?  │
│              │                                                │
│              ▼                                                │
│     RETRIEVER-REASONER AGENT                                  │
│       Tool 1: vector_search(query) → Chroma similarity search │
│       Tool 2: get_parcel_attributes(apn) → parcel table lookup│
│       → judges sufficiency of results, retries refined query  │
│         up to 2x if insufficient                               │
│              │                                                │
│              ▼                                                │
│     RAG GENERATION                                             │
│       → combines retrieved doc text + parcel attrs + question │
│       → calls OpenRouter LLM → grounded answer w/ citations   │
│              │                                                │
│              ▼                                                │
│     VALIDATOR AGENT                                            │
│       → checks answer claims are actually supported by         │
│         retrieved context + parcel data                        │
│       → if unsupported, triggers stricter regeneration          │
│              │                                                │
│              ▼                                                │
│     Response + sources → returned to frontend                 │
└─────────────────────────────────────────────────────────────┘
```

### Why this is "agentic" and not plain RAG
Plain RAG retrieves once and answers regardless of quality. Here:
- The Retriever-Reasoner **evaluates its own retrieval** and can retry with a refined
  query if insufficient.
- The Retriever-Reasoner **chooses between two heterogeneous tools** (vector search vs.
  parcel lookup) based on the Planner's assessment of what's needed.
- The Validator **checks the final answer against sources** and can trigger regeneration.

These self-correction loops are the graded differentiator between "RAG" and "Agentic RAG."

---

## 4. Real Data On Hand

### 4a. Parcel data (Palo Alto, CA — used as the demo city)

Source: Palo Alto GIS parcel shapefile, converted to CSV, ~21,179 rows (one row per
parcel). File: `_PaloAltoShapeFile27062025__202608071640.csv` (already explored).

**Relevant columns (full list has 70+ columns, these are the ones that matter):**

| Column | Type | Meaning | Sample value |
|---|---|---|---|
| `APN` | string | Assessor Parcel Number (primary key) | `127-53-008` |
| `UNITS` | int | Number of residential units on parcel | `30` |
| `ZONEGIS` | string | Zoning code | `RM-20`, `R-1` |
| `LANDUSEGIS` | string | Land use category | `MF` (multi-family), `SF` (single-family) |
| `YEARBUILT` | int | Construction year | `1961` |
| `STORIES` | int | Number of stories | `2` |
| `BUILDINGSQ` | int | Building square footage | `3403` |
| `LOTSQFT` | int | Lot square footage | `6969` |
| `HRBCATEGOR` | string | Historic Resources Board category (may be null) | `null` or category text |
| `FLOODZONE` | string | FEMA flood zone | `AE10.5` |
| `Geometry` | string (WKT) | Parcel polygon geometry for map rendering | `MULTIPOLYGON(((...)))` |
| `GeometryJsonb` | string (JSON) | Same geometry as GeoJSON | `{"type":"MultiPolygon",...}` |
| `ZIP` | string | Zip code | `94303` |
| `JURISDICTI` | string | City jurisdiction | `Palo Alto` |

**Key distribution facts (already verified via pandas):**
- 267 parcels have `UNITS >= 10`
- 933 parcels have `2 <= UNITS < 10`
- ~19,979 parcels have `UNITS <= 1` (effectively single-family, most exemptions apply)

**What this data does NOT have (and no public parcel dataset ever will):**
`occupancy_status`, `rent_registry_status`, `last_inspection_date`, `bedroom_count`.
These are internal housing-department case records or lease-level details, not
assessor/GIS attributes. If a question needs these, either:
(a) the user must state it in the chat question (e.g., "for a 2-bedroom unit..."), or
(b) build a small supplemental CSV joined on APN (optional, not required for MVP).

### 4b. Ordinance document (Palo Alto Municipal Code, Chapter 9.68)

Source: Palo Alto Municipal Code, Title 9 (Public Peace, Morals and Safety),
**Chapter 9.68 — Rental Housing Stabilization**. Full text already extracted (see
`docs/chapter_9_68_full_text.md` — to be created from the pasted content in this
project's history). Sections:

- 9.68.010 Purpose
- 9.68.020 Definitions (just cause, landlord, rent, renter, residential rental unit, security)
- 9.68.030 Requirement of offering one-year written leases (+ 12 exemption categories)
- 9.68.040 Just-cause evictions required (+ 8 exemption categories, 6-month protection rule)
- 9.68.050 General relocation assistance/rent waiver for no-fault eviction (1 month's rent)
- **9.68.060 Relocation assistance for evictions in structures/lots with 10+ units**
  — THIS is the section with a real numeric threshold tied to the `UNITS` column, and
  a bedroom-based dollar table:
  ```
  0 bedrooms: $7,000   |  1 bedroom: $9,000
  2 bedrooms: $13,000  |  3+ bedrooms: $17,000
  (+$3,000 if renter is low-income/60+/disabled/minor)
  (annual CPI adjustment; half paid at notice, half at move-out)
  ```
- 9.68.070 Security deposit limit (1.5 months' rent for unfurnished units)
- 9.68.080 Renter's remedies
- 9.68.090 Nonwaiver

**Important reasoning note:** the $13,000-style figures are **literal values retrieved
from the document**, not computed by the LLM. The agent's job is to (1) use `UNITS` to
pick the correct rule section (9.68.060 vs 9.68.050), (2) use the user-stated bedroom
count to pick the correct table row, and (3) do the one piece of actual arithmetic:
splitting the total in half (notice payment + move-out payment). Do not let the LLM
"calculate" the base dollar amount — it must be retrieved verbatim from the chunk.

---

## 5. Example Use Case (reference implementation target)

**User:** selects parcel APN `127-53-008` on the map, asks: *"If a tenant with a
2-bedroom unit here is evicted without fault, how much relocation assistance is owed?"*

**Expected flow:**
1. Planner: needs both document rule (relocation assistance for no-fault eviction) AND
   parcel attributes (unit count, to know which section applies).
2. Retriever-Reasoner:
   - `search_documents("relocation assistance no-fault eviction")` → retrieves chunks
     for both 9.68.050 and 9.68.060.
   - `get_parcel_attributes("127-53-008")` → returns `{UNITS: 30, ZONEGIS: "RM-20", ...}`.
   - Reasoning: `UNITS = 30 >= 10` → **9.68.060 applies**, not 9.68.050.
3. Generation: looks up "2 bedrooms" row in the 9.68.060(b)(1) table → `$13,000`. Notes
   the 50/50 split ($6,500 at notice, $6,500 at move-out).
4. Validator: confirms `$13,000` appears verbatim in the retrieved chunk and `30 units`
   matches the parcel tool's real output. Approves.
5. Response: "This parcel has 30 units, so it falls under Section 9.68.060 (10+ unit
   structures). For a 2-bedroom unit, relocation assistance is $13,000 total — $6,500
   paid at notice, $6,500 at move-out. [Source: PAMC 9.68.060(b)(1)]"

Use this exact example as the primary test case when the agent loop is built — if this
answer comes out wrong, something in the tool logic or prompt is broken.

---

## 6. Tech Stack (decided, no LangChain — plain Python, since dev is not yet comfortable with LangChain)

| Layer | Tech |
|---|---|
| Frontend | React + Esri ArcGIS JS SDK |
| Backend | FastAPI (Python) |
| Document parsing | `pypdf` (PDF), plain file read (TXT), `pandas` (CSV/Excel) |
| Chunking | Custom Python function — **chunk by section number** (e.g., 9.68.010, .020...) not raw character count, since each section is a self-contained legal unit |
| Vector store | `chromadb` (local, persisted to disk, no external service) |
| Embeddings | `sentence-transformers` (local, free — OpenRouter is chat-completion only, not embeddings) |
| Parcel data | `pandas` — load CSV, query by APN via plain dict/dataframe lookup (NOT vector search — this is structured data) |
| LLM | OpenRouter API (user already has a key) — call via plain `requests.post()` to `https://openrouter.ai/api/v1/chat/completions` |
| Agents | Plain Python classes/functions — `PlannerAgent`, `RetrieverReasonerAgent`, `ValidatorAgent` — each is just a class wrapping LLM calls + tool calls in a loop. No agent framework. |
| Deployment (later) | Backend: Render/Railway. Frontend: Vercel/Netlify. Decide specifics closer to week 3. |

**Explicitly rejected for now:** LangChain, LlamaIndex — developer wants to understand
the raw mechanics (tokenizer, embeddings, agent loop) before adopting a framework that
abstracts them away. Do not introduce these without being asked.

---

## 7. Folder Structure

```
gis-agentic-rag-capstone/
│
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI entrypoint, routes
│   │   ├── config.py                # env vars, OpenRouter key, paths
│   │   │
│   │   ├── routers/
│   │   │   ├── upload_shapefile.py  # POST /upload/shapefile
│   │   │   ├── upload_document.py   # POST /upload/document
│   │   │   ├── parcel_search.py     # GET /parcel/search?apn=...
│   │   │   └── query.py             # POST /query (chat)
│   │   │
│   │   ├── ingestion/
│   │   │   ├── shapefile_loader.py  # parse shapefile/CSV -> geometry + attributes
│   │   │   ├── document_loader.py   # PDF/TXT/CSV/Excel -> raw text
│   │   │   └── chunker.py           # split text into chunks (by section)
│   │   │
│   │   ├── vectorstore/
│   │   │   ├── embeddings.py        # sentence-transformers wrapper
│   │   │   └── chroma_client.py     # chroma init, add, search
│   │   │
│   │   ├── parcel_data/
│   │   │   ├── parcel_store.py      # load/query parcel table by APN
│   │   │   └── schema.py            # expected column definitions
│   │   │
│   │   ├── agents/
│   │   │   ├── planner_agent.py
│   │   │   ├── retriever_reasoner_agent.py
│   │   │   ├── validator_agent.py
│   │   │   └── orchestrator.py      # ties agents together, runs the loop
│   │   │
│   │   ├── llm/
│   │   │   └── openrouter_client.py # call OpenRouter API
│   │   │
│   │   └── guardrails/
│   │       └── validators.py        # input checks, error handling
│   │
│   ├── data/
│   │   ├── uploaded_shapefiles/     # user-uploaded shapefiles/CSVs land here
│   │   ├── uploaded_documents/      # user-uploaded PDFs/TXT/CSV/Excel
│   │   └── chroma_store/            # persisted vector DB
│   │
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── MapView.jsx          # Esri map, renders parcels
│   │   │   ├── ShapefileUpload.jsx  # upload control for shapefile
│   │   │   ├── DocumentUpload.jsx   # upload control for PDF/etc.
│   │   │   ├── ApnSearch.jsx        # search box for APN
│   │   │   └── ChatPanel.jsx        # question/answer UI
│   │   │
│   │   ├── api/
│   │   │   └── client.js            # fetch wrappers to backend endpoints
│   │   │
│   │   └── state/
│   │       └── selectedParcel.js    # shared state: currently selected APN
│   │
│   ├── package.json
│   └── public/
│
├── docs/
│   ├── README.md                    # architecture write-up (task 10)
│   └── chapter_9_68_full_text.md    # source ordinance text for reference
│
└── .gitignore
```

---

## 8. Build Order (3-week plan)

**Week 1 — Backend core, no agents yet:**
1. Project scaffolding (folders above, FastAPI hello-world, requirements.txt)
2. `document_loader.py` + `chunker.py` — ingest Chapter 9.68 PDF, chunk by section
3. `embeddings.py` + `chroma_client.py` — embed chunks, store, test similarity search
4. `parcel_store.py` — load Palo Alto CSV, implement `get_parcel_attributes(apn)`
5. `openrouter_client.py` — basic call working end to end
6. Plain RAG working: retrieve once → generate → done (no self-correction yet).
   **Milestone: can answer "what's the security deposit limit?" correctly.**

**Week 2 — Agent layer + GIS integration (highest risk week):**
1. `planner_agent.py` — decompose question, decide which tools needed
2. `retriever_reasoner_agent.py` — call both tools, sufficiency check, retry logic
3. `validator_agent.py` — hallucination check against sources
4. `orchestrator.py` — wire the loop together
5. Frontend: `MapView.jsx` with Esri SDK rendering parcel geometry from CSV
6. Frontend: `ApnSearch.jsx`, click-to-select, wire to `ChatPanel.jsx`
   **Milestone: the full example use case in Section 5 works end-to-end.**

**Week 3 — Polish, guardrails, deploy, document:**
1. `ShapefileUpload.jsx` / `DocumentUpload.jsx` — make ingestion generic/reusable for
   any city (not hardcoded to Palo Alto)
2. `guardrails/validators.py` — input validation, retry caps, error messages
3. Deploy backend (Render/Railway) + frontend (Vercel/Netlify)
4. Write `docs/README.md` — architecture diagram, why agentic not plain RAG, limitations

**Fallback if behind schedule:** ship the pure document-agent-RAG version (no GIS)
fully working by end of week 2 — it alone satisfies all 10 capstone tasks. Add GIS in
week 3 only if time remains.

---

## 9. Known Limitations (for README task 10)

- Parcel dataset lacks occupancy status, rent registry status, inspection history, and
  bedroom count — these are internal administrative records unavailable in any public
  GIS dataset. Bedroom count must be supplied by the user in their question.
- Retrieval sufficiency and hallucination checks are themselves LLM calls, so they
  inherit the base model's reliability limits — mitigation, not a guarantee.
- No re-ranking model; relies on raw embedding similarity search only.
- Single vector store per session; no incremental re-indexing of updated documents.
- No authentication/multi-user document isolation — acceptable for a capstone demo.

---

## 10. Open Decisions (not yet finalized — flag if asked)

- Exact OpenRouter model choice (cost vs. quality tradeoff) — not yet picked.
- Whether APN search supports fuzzy matching or exact-match only (current plan:
  exact-match only, mention fuzzy as future work).
- Final deployment targets — mentioned as defaults above, not committed.
- Whether to add Chapter 9.65 (Residential Rental Registry Program) as a second
  document — currently out of scope, Chapter 9.68 alone is sufficient.
