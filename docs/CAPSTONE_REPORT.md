# Exon Rental — Agentic RAG over Municipal Ordinances + GIS Parcel Data

**Capstone Report**

| | |
|---|---|
| **Project** | Exon Rental — parcel-aware rental housing compliance assistant |
| **Demo city** | Palo Alto, California |
| **Repository** | `paloAltoRentalGIS` |
| **Stack** | FastAPI · LangChain (components only) · Chroma · sentence-transformers · OpenRouter (Claude Sonnet 4.5) · React 19 + Vite · Esri ArcGIS JS SDK |
| **Deployment** | Azure App Service (backend) + Azure Static Web Apps (frontend) |

---

## Table of contents

1. [The problem in one page](#1-the-problem-in-one-page)
2. [What the system does](#2-what-the-system-does)
3. [Architecture at a glance](#3-architecture-at-a-glance)
4. [Pipeline A — Ingestion (document → vectors)](#4-pipeline-a--ingestion-document--vectors)
5. [Pipeline B — Query (question → verified answer)](#5-pipeline-b--query-question--verified-answer)
6. [Chunking, in detail](#6-chunking-in-detail)
7. [Embeddings and similarity search](#7-embeddings-and-similarity-search)
8. [Merging retrieval with the LLM](#8-merging-retrieval-with-the-llm)
9. [The agents — role, input, output, failure mode](#9-the-agents--role-input-output-failure-mode)
10. [Validation states and what each one means](#10-validation-states-and-what-each-one-means)
11. [The reasoning trace](#11-the-reasoning-trace)
12. [Plain RAG vs Agentic RAG — the measured difference](#12-plain-rag-vs-agentic-rag--the-measured-difference)
13. [Test cases and results](#13-test-cases-and-results)
14. [Reliability and safety controls](#14-reliability-and-safety-controls)
15. [Deployment](#15-deployment)
16. [Known limitations](#16-known-limitations)
17. [Roadmap](#17-roadmap)
18. [Assignment task mapping](#18-assignment-task-mapping)
19. [Appendix — API reference](#19-appendix--api-reference)
20. [Appendix — Running locally](#20-appendix--running-locally)

---

## 1. The problem in one page

A tenant facing a no-fault eviction wants to know what they are owed. The answer needs
two facts that live in two systems that never talk to each other:

| Fact | Where it lives | Form |
|---|---|---|
| *"Buildings with 10+ rental units owe $13,000 for a 2-bedroom."* | Municipal ordinance | Unstructured legal PDF |
| *"This building has 30 units."* | County GIS parcel layer | Structured attribute table |

Neither source answers the question alone. The ordinance does not know how many units
*this* building has. The GIS layer knows the unit count but nothing about the law.

A generic document chatbot reads the PDF and stops. It will confidently quote a figure
from a rule that does not apply to the user's building — the answer is fluent, cited,
and wrong.

**This project joins the two, so the answer depends on the specific parcel.**

> Click a 30-unit building → **$13,000**
> Click the single-family house next door → **one month's rent**
> Same question. Different answers. Both correct. Both cited.

> **IMAGE PLACEHOLDER — Figure 1**
> `docs/images/01-hero-two-answers.png`
> *Side-by-side screenshot: the same question asked against a 30-unit parcel and a
> single-family parcel, showing the two different answers and their different source
> chips. This is the single most important screenshot in the report.*

---

## 2. What the system does

1. **Upload an ordinance PDF** → parsed, chunked section-by-section, embedded, stored
   in a persistent vector database.
2. **Upload a parcel shapefile** (`.zip`) for any city → parsed entirely in the browser,
   rendered as a layer on an Esri map.
3. **Click a parcel** → its real GIS attributes become the context for the next question.
4. **Ask in plain English** → a four-agent pipeline plans, retrieves, judges its own
   retrieval, generates, and independently verifies the answer.

Every answer carries three artefacts of accountability:

| Artefact | What it proves |
|---|---|
| **Source chips** — `9.68.060 · 0.612` | Which ordinance sections were used, and how relevant each was |
| **Validation badge** — `✓ verified` | A second, independent model pass found every claim traceable to a source |
| **Reasoning trace** — plan, tools, queries | What the system decided to do, and whether it had to try twice |

> **IMAGE PLACEHOLDER — Figure 2**
> `docs/images/02-full-ui.png`
> *Full application window: icon rail (left), map with a selected highlighted parcel
> (centre), chat panel with an answered question (right), top bar showing feature and
> document counts. Annotate the three accountability artefacts with callouts.*

---

## 3. Architecture at a glance

```
┌─────────────────────────── BROWSER (React 19 + Vite) ───────────────────────────┐
│                                                                                 │
│  IconRail ─▶ Drawer ─▶ [Layers | Add data | Documents | Find parcel | Basemap]   │
│                                                                                 │
│  MapView (Esri ArcGIS JS 4.31)          ChatPanel                               │
│    · GeoJSONLayer from shpjs              · question input                       │
│    · view.on("click") → hitTest           · source chips                        │
│    · → { apn, attributes }                · validation badge                    │
│                                           · collapsible trace                   │
│         shapefile.zip parsed HERE — the backend never sees it                    │
└───────────────────┬────────────────────────────────┬────────────────────────────┘
                    │ POST /api/upload_document      │ POST /api/query
                    │ (multipart PDF)                │ { question, apn,
                    │                                │   parcel_attributes }
┌───────────────────▼────────────────────────────────▼────────────────────────────┐
│                          BACKEND (FastAPI, Python 3.11)                          │
│                                                                                  │
│  PIPELINE A — INGESTION (no LLM)        PIPELINE B — QUERY (LLM agents)           │
│  ────────────────────────────────       ─────────────────────────────────         │
│  document_loader.py                     orchestrator.py                           │
│      PyPDFLoader → 1 Doc/page               1. planner_agent                       │
│  chunker.py                                 2. retriever_reasoner_agent            │
│      section split → size enforce              ├── search_sections()  ◀── tool 1   │
│  chroma_client.add_documents()                 └── get_parcel_attributes() ◀─ tool 2│
│      stable id + embed + persist            3. generator_agent                     │
│                                             4. validator_agent                     │
│                    ┌───────────────────────────────────────────┐                  │
│                    │ Chroma (embedded, data/chroma_store/)     │                  │
│                    │ all-MiniLM-L6-v2 · 384-dim · normalized   │                  │
│                    └───────────────────────────────────────────┘                  │
│                                  │                                                │
│                                  ▼  OpenRouter → anthropic/claude-sonnet-4.5      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Two heterogeneous tools.** This matters for the "agent uses tools" requirement:
the agents choose between a *semantic* tool (vector search over legal prose) and a
*structured* tool (exact attribute lookup on a parcel). They are not two flavours of
the same search.

> **IMAGE PLACEHOLDER — Figure 3**
> `docs/images/03-architecture.png`
> *Clean redrawn architecture diagram (draw.io / Excalidraw) of the ASCII block above.
> Colour-code: blue = browser, green = ingestion, orange = agents, grey = storage.*

---

## 4. Pipeline A — Ingestion (document → vectors)

This pipeline contains **no LLM call at all**. Chunking a PDF has one correct answer;
there is nothing to reason about. Agents appear only at query time.

### Step-by-step

```
User picks Palo_Alto_9.68.pdf in the Documents drawer
   │
   ▼  DocumentsPanel.jsx → api/client.js
POST /api/upload_document        (multipart/form-data, field name "file")
   │
   ▼  routers/upload_document.py
1. safe_name = Path(file.filename).name        ← blocks "..\..\app\config.py"
2. suffix in ALLOWED_SUFFIXES ?                ← validated BEFORE writing to disk
3. contents non-empty ?
4. write to data/uploaded_documents/
   │
   ▼  ingestion/document_loader.py
5. PyPDFLoader(path).load()   →  7 Documents, one per page
6. assert some page has text  →  else "may be a scanned image needing OCR"
7. stamp metadata["source_file"] = filename    ← the citation key, set once, here
   │
   ▼  ingestion/chunker.py
8.  join all pages into one string   ← a section can straddle a page break
9.  regex-find section headings
10. keep the LAST match per section number     ← drops the table-of-contents copy
11. cut heading → next heading                 →  9 sections
12. drop bodies under 200 chars                ← leftover TOC fragments
13. sub-split anything over 1000 chars         →  37 chunks
   │
   ▼  vectorstore/chroma_client.py
14. id = "source_file::section::part"          ← re-upload OVERWRITES, never duplicates
15. Chroma embeds each chunk → 384 floats, L2-normalized
16. persist to data/chroma_store/
   │
   ▼
200 {"filename": "...", "pages": 7, "chunks": 37, "sections": [9 numbers]}
```

### The router

```python
ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".xlsx", ".xls"}

@router.post("/upload_document")
def upload_document(file: UploadFile = File(...)):
    # Deliberately sync: parsing and embedding are CPU-bound with nothing to await,
    # so FastAPI runs this in a threadpool and the event loop stays free.
    # Path(...).name strips any directory component — `filename` is client-supplied,
    # so "..\..\app\config.py" would otherwise write outside the upload folder.
    safe_name = Path(file.filename or "").name
    ...
    try:
        docs = load_documents(file_path)
        chunks = chunk_documents(docs)
        add_documents(chunks)
    except (UnsupportedFileType, ValueError) as err:
        # Readable problems with the file itself — don't keep the bad upload.
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(err)) from err
```

Three deliberate decisions in that block:

- **Sync `def`, not `async def`.** PDF parsing and embedding are CPU-bound with nothing
  to `await`. FastAPI runs a sync route in a threadpool, so the event loop stays free;
  an `async def` doing blocking work would stall every other request.
- **Extension checked before the write.** Validating after writing means a rejected file
  still landed on disk.
- **Failed ingestion deletes the file.** Otherwise a corrupt upload stays on disk
  forever, un-indexed and invisible.

> **IMPLEMENTATION NOTE — worth stating honestly in the report.**
> The router advertises six extensions, but `document_loader.load_documents()` currently
> implements **only `.pdf`** and raises `UnsupportedFileType` for everything else. A
> `.csv` upload therefore passes the router's check and then fails at load with a 400.
> The dispatch structure for TXT/CSV/Excel is in place; the branches are not wired.

> **IMAGE PLACEHOLDER — Figure 4**
> `docs/images/04-upload-result.png`
> *Documents drawer immediately after a successful upload, showing the returned
> `pages / chunks / sections` summary. Optionally pair it with the raw JSON response
> from `/docs`.*

---

## 5. Pipeline B — Query (question → verified answer)

```
User clicks parcel 127-53-008 on the map, types a question
   │
   ▼  MapView.jsx
view.on("click") → view.hitTest(event) → graphic.attributes
   → { apn: "127-53-008", attributes: { UNITS: 30, ZONEGIS: "RM-40", ... } }
   │
   ▼  App.jsx (selectedParcel state) → ChatPanel.jsx → api/client.js
POST /api/query { question, apn, parcel_attributes }
   │
   ▼  routers/query.py  (Pydantic validation: question 1–2000 chars)
   ▼  agents/orchestrator.py
   │
   ├── 1. PLANNER ───────────────────────────────────────────── LLM call #1
   │      in : question, has_apn (bool), parcel field NAMES (not values)
   │      out: { needs_documents, needs_parcel, search_query, reasoning }
   │      e.g. "how much do I get if I'm kicked out?"
   │             → search_query: "relocation assistance eviction without fault"
   │
   ├── 2. RETRIEVER-REASONER
   │      ├─ get_parcel_attributes(apn, raw)   ← ONCE, outside the loop
   │      │                                      (a dict lookup can't change)
   │      └─ loop, attempt = 1 .. 3:
   │           ├─ search_sections(query)        ← local embeddings, no API, no cost
   │           ├─ keep only score > MIN_SCORE (0.15)
   │           ├─ _summarize_findings()         ← section LABELS only, cheap
   │           ├─ check_sufficiency(...)  ────────────────────── LLM call #2
   │           └─ sufficient ? break
   │              : better_query already tried or empty ? break
   │              : query = better_query, loop again
   │
   ├── 3. GENERATOR ─────────────────────────────────────────── LLM call #3
   │      in : question, FULL section text, parcel attributes
   │      out: grounded prose answer with [Section N] citations
   │
   └── 4. VALIDATOR ─────────────────────────────────────────── LLM call #4
          in : the answer + the same sources the generator saw (full text, no scores)
          out: { supported, unsupported_claims, checked }
   │
   ▼
200 { answer, sources[], parcel, validation{}, trace{} }
   │
   ▼  ChatPanel.jsx
answer text · source chips · validation badge · collapsible reasoning trace
```

### LLM call budget

| Call | Agent | `max_tokens` | Runs |
|---|---|---|---|
| 1 | Planner | 300 | always, once |
| 2 | Sufficiency check | 300 | once per retrieval attempt (1–3×) |
| 3 | Generator | 800 | always, once |
| 4 | Validator | 500 | always, once |

**Typical: 4 calls, ~6–10 seconds. Worst case: 6 calls** (three retrieval attempts).
Every call uses `temperature=0.0` — grounded legal answers should be repeatable, not
creative. Plain RAG would be one call and ~2 seconds; the extra latency *is* the
self-checking behaviour.

### The orchestrator, in full

It holds no logic beyond sequencing. It owns the request data and hands each agent only
what that agent needs — which is why the planner never sees attribute values and the
generator never sees a search API.

```python
def answer(question, apn=None, parcel_attributes=None) -> dict:
    """Plan, retrieve, reason, generate, validate."""
    # 1. Planner — gets the parcel's field NAMES but not their values.
    the_plan = plan(
        question,
        has_apn=bool(apn),
        parcel_fields=list(parcel_attributes.keys()) if parcel_attributes else None,
    )

    # 2. Retriever-reasoner — calls the tools, judges the results, retries search.
    found = retrieve_and_reason(question, the_plan, apn, parcel_attributes)

    # 3. Generator — writes the answer from what was gathered.
    result = generate_answer(question, found["documents"], found["parcel"])

    # 4. Validator — checks the answer against the same sources the generator saw.
    validation = validate(question, result["answer"], found["documents"], found["parcel"])

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "parcel": found["parcel"],
        "validation": validation,
        "trace": {
            "plan": the_plan,
            "sufficient": found["sufficient"],
            "attempts": found["attempts"],
            "queries": found["queries"],
            "notes": found["notes"],
        },
    }
```

> **IMAGE PLACEHOLDER — Figure 5**
> `docs/images/05-query-sequence.png`
> *Sequence diagram (UML-style, or Mermaid `sequenceDiagram`) with lifelines for:
> Browser → FastAPI → Orchestrator → Planner → Reasoner → Chroma → ParcelStore →
> Generator → Validator. Mark the four LLM calls with a distinct arrow style and label
> the retry loop as a `loop [max 3]` box.*

---

## 6. Chunking, in detail

### Why section-aware, not fixed-size

A legal section is a **self-contained rule**. Cut it at an arbitrary 1000 characters and
you can retrieve the dollar table of §9.68.060 without the sentence that says the whole
section only applies to buildings with 10+ units. The retrieval looks perfect; the answer
is wrong. Section boundaries are the natural semantic unit of a municipal code, so the
chunker respects them first and only falls back to size.

### Stage 1 — the heading regex

```python
# Matches a heading like "9.68.060   Relocation assistance..."
# Generic (\d+\.\d+\.\d+) so it works for any city's code.
# The 2+ spaces requirement stops mid-sentence cross-references such as
# "see Section 9.68.050 for..." from being read as headings.
SECTION_RE = re.compile(
    r"(?m)^\s*"
    # Optional prefix used by some codes: "§ 8.52.030", "Sec. 12-45", "Section 9.68.060"
    r"(?:§\s*|Sec\.?\s+|Section\s+)?"
    # 2 to 4 parts, dot- or hyphen-separated: 9.68.060, 12-45, 37.02.010
    r"(?P<num>\d+(?:[.-]\d+){1,3})"
    r"\s{2,}(?P<title>[A-Z][^\n]*)"
)
```

Four constraints, each earning its place:

| Constraint | Why |
|---|---|
| `(?m)^\s*` | A heading starts a line. A number mid-sentence is a cross-reference. |
| optional `§` / `Sec.` / `Section` prefix | Added after San Joaquin's code used `§ 150.060`. |
| `\s{2,}` before the title | Two-plus spaces is the typographic signature of a heading. `"see Section 9.68.050 for details"` has one space and is correctly ignored. |
| `[A-Z]` title start | Headings are title-case; prose continuations are not. |

### Stage 2 — dropping the table of contents

Every section number appears **twice** in these PDFs: once in the front-matter contents
list, once as the real heading. Keeping the *last* match per number discards the TOC copy
without needing to detect where the TOC ends.

```python
# Each section number appears twice: once in the table of contents, once as
# the real heading. Keeping the LAST match per number drops the TOC copy.
headings = sorted(
    {m.group("num"): m for m in matches}.values(), key=lambda m: m.start()
)

for i, match in enumerate(headings):
    end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
    body = _tidy(text[match.start() : end])

    if len(body) < 200:  # leftover TOC fragment — title with no rule text
        continue
```

Dict comprehension over an ordered iterator: each key's value is overwritten by later
matches, so only the final occurrence survives. Re-sorting by position restores document
order. The `< 200` guard catches any TOC line the trick misses.

### Stage 3 — size enforcement

`all-MiniLM-L6-v2` silently truncates input past ~256 tokens (~1000 characters). Silently
is the dangerous word: an oversized chunk embeds *only its beginning*, so the rest is
unsearchable and nothing warns you. Oversized sections are therefore sub-split:

```python
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)

def _enforce_size(sections: list[Document]) -> list[Document]:
    """Sub-split oversized sections, keeping each piece's section metadata."""
    out = []
    for doc in sections:
        if len(doc.page_content) <= 1000:
            doc.metadata["part"] = 1
            doc.metadata["parts"] = 1
            out.append(doc)
            continue

        pieces = _splitter.split_documents([doc])
        for n, piece in enumerate(pieces, start=1):
            # metadata is copied by the splitter, so section/title survive.
            piece.metadata["part"] = n
            piece.metadata["parts"] = len(pieces)
            out.append(piece)
    return out
```

`part` / `parts` are the crucial addition — they are what makes reassembly possible at
query time (§7). The separator order degrades gracefully: paragraph → line → sentence →
word → character, so a cut lands at the largest structural boundary available.

### Stage 4 — deliberate non-cleanup

```python
def _tidy(text: str) -> str:
    """Light cleanup only — deliberately does NOT collapse runs of spaces, since
    the 9.68.060 dollar table may rely on spacing to pair bedrooms with amounts."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
```

The obvious "normalise whitespace" step would destroy the ordinance's dollar table.
`"2 bedroom      $13,000"` collapsed to single spaces loses the column alignment that
pairs the bedroom count with its amount.

### Fallback

```python
sections = _split_sections(full_text, source)
if not sections:
    # No section numbering — plain recursive splitting.
    return _splitter.split_documents(docs)
```

Any PDF still ingests. A document with unrecognised numbering loses the
rule-stays-with-its-exemptions guarantee but remains searchable — degraded, not broken.

### Result on the demo document

| Metric | Value |
|---|---|
| Pages | 7 |
| Sections detected | 9 |
| Final chunks | 37 |
| Largest section | 9.68.060 → 7 parts |

> **IMAGE PLACEHOLDER — Figure 6**
> `docs/images/06-chunking.png`
> *Visual walkthrough: (a) a page of the raw ordinance PDF with headings circled,
> (b) the same content as 9 section blocks, (c) §9.68.060 exploded into its 7 parts with
> `part`/`parts` metadata shown. This one figure carries the whole chunking story.*

---

## 7. Embeddings and similarity search

### The embedding model

```python
@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Load the model once and reuse it."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,                    # all-MiniLM-L6-v2
        model_kwargs={"device": "cpu"},
        # Normalizing makes cosine similarity behave predictably.
        encode_kwargs={"normalize_embeddings": True},
    )
```

| Property | Value | Why it was chosen |
|---|---|---|
| Model | `sentence-transformers/all-MiniLM-L6-v2` | Strong quality-per-megabyte for short passages |
| Dimensions | 384 | Compact index, fast cosine |
| Size | ~90 MB | Fits comfortably in an App Service worker |
| Context | 256 tokens | **Sets the chunker's 1000-char limit** |
| Cost | Free, runs locally | The only paid dependency is the chat LLM |

`@lru_cache(maxsize=1)` matters more than it looks: loading takes several seconds and
holds ~90 MB. Without the cache, every single search would reload the model from disk.
`normalize_embeddings=True` makes every vector unit-length, so cosine similarity is not
skewed by chunk length — a long section would otherwise look systematically different
from a short one for reasons that have nothing to do with meaning.

### Stable IDs — the idempotent-upload trick

```python
def _chunk_id(doc: Document) -> str:
    """Stable id built from the chunk's own metadata.

    Re-uploading the same document overwrites these rows instead of storing a
    second copy of every chunk — without this, uploading twice would duplicate
    every search result.
    """
    m = doc.metadata
    return f"{m.get('source_file', 'unknown')}::{m.get('section', '0')}::{m.get('part', 1)}"
```

`Palo_Alto_9.68.pdf::9.68.060::3` is deterministic. Re-uploading an amended ordinance
updates the rows in place. Without this, Chroma assigns random UUIDs and the second
upload doubles every result — the same section retrieved twice, consuming two of the four
context slots.

### The retrieval score floor

```python
# Correct sections score 0.5-0.7 in testing; irrelevant ones land under 0.1.
# Anything below this is noise that only burns tokens.
MIN_SCORE = 0.15
```

Vector search *always* returns `k` results — it has no concept of "nothing matched". Ask
about parking in a document that never mentions parking and you still get four sections,
scoring ~0.05. Without a floor those four irrelevant sections enter the prompt and invite
the model to improvise. The floor is what makes "I couldn't find anything relevant" a
reachable outcome. The 0.15 threshold sits in the empirically empty gap between 0.1 and
0.5.

### `search_sections` — the retrieval that makes the answers correct

This function is the heart of the retrieval quality.

```python
def search(query: str, k: int = 4, source_file: str | None = None):
    """Raw similarity search. Returns [(Document, score), ...], best first."""
    where = {"source_file": source_file} if source_file else None
    return get_store().similarity_search_with_relevance_scores(query, k=k, filter=where)


def search_sections(query: str, k: int = 4, source_file: str | None = None):
    """Search, then return whole sections instead of fragments.

    A section split across parts can hold a rule in one chunk and its exemption
    in another — 9.68.060 splits into 7. Re-joining the parts means the LLM always
    sees the complete rule alongside its exceptions.
    """
    results = []
    seen = set()

    for doc, score in search(query, k=k * 4, source_file=source_file):
        meta = doc.metadata
        key = (meta.get("source_file"), meta.get("section"))

        if key in seen:
            continue
        seen.add(key)

        if meta.get("parts", 1) > 1 and all(key):
            results.append((get_full_section(*key) or doc, score))
        else:
            results.append((doc, score))

        if len(results) >= 4:
            break

    return results
```

Read as four moves:

1. **Over-fetch `k*4` = 16 chunks.** Because the next step throws most of them away.
2. **Dedup by `(source_file, section)`.** §9.68.060 has 7 parts; a good query often
   matches five of them. Naively, five of your four context slots are one section.
   Deduping means four *distinct* sections reach the LLM.
3. **Stitch split sections back together.** When `parts > 1`, replace the matching
   fragment with the whole reassembled section.
4. **Keep the best fragment's score** as the section's score, so the ranking still
   reflects the strongest match.

```python
def get_full_section(source_file: str, section: str) -> Document | None:
    """Rebuild a complete section from its stored parts."""
    rows = get_store().get(
        where={"$and": [{"source_file": {"$eq": source_file}},
                        {"section":     {"$eq": section}}]}
    )
    if not rows["ids"]:
        return None

    ordered = sorted(
        zip(rows["metadatas"], rows["documents"]),
        key=lambda pair: pair[0].get("part", 1),
    )

    meta = dict(ordered[0][0])
    meta.pop("part", None)          # the rebuilt section isn't a part of anything
    meta.pop("parts", None)

    return Document(page_content="\n".join(text for _, text in ordered), metadata=meta)
```

**This is why the system gets the eviction question right.** §9.68.060 splits into 7
parts. The dollar table is in one part; the sentence *"this section applies to structures
containing ten or more residential rental units"* is in another. Retrieve the table alone
and the model hands a 30-unit figure to a single-family homeowner. Rejoining guarantees
the rule and its exemptions arrive together — a chunking decision (`part`/`parts`) paying
off two pipelines later.

> **IMAGE PLACEHOLDER — Figure 7**
> `docs/images/07-search-sections.png`
> *Funnel diagram: 16 raw chunk hits → dedup by section → 4 distinct sections → 2 of them
> reassembled from parts → final context. Show, side by side, "what the LLM would have
> seen without stitching" (dollar table, no threshold) vs "with stitching" (rule +
> exemption). This figure justifies the whole retrieval design.*

---

## 8. Merging retrieval with the LLM

Retrieved sections are not passed as metadata — the model cannot see metadata. They are
formatted into labelled text blocks so that the section number is **inside the string the
model reads**, which is the only way it can produce a real citation.

```python
def build_context(results: list[tuple]) -> str:
    """Format retrieved sections into labeled blocks for the prompt.

    The section number has to appear in the text itself — the model can't see
    metadata, so this is the only way it can cite a real source.
    """
    blocks = []
    for i, (doc, _score) in enumerate(results, start=1):
        meta = doc.metadata
        blocks.append(
            f"[Source {i}] Section {meta.get('section')} - {meta.get('title', '')}\n"
            f"{doc.page_content}"
        )

    return "\n\n---\n\n".join(blocks)
```

### The grounding contract

Five rules, shared by the plain-RAG baseline and the agent generator:

```python
SYSTEM_PROMPT = """You are a rental housing compliance assistant. Answer using ONLY \
the municipal code excerpts provided in the user message.

Rules:
1. Quote dollar amounts, time periods, and numeric thresholds EXACTLY as they appear \
in the excerpts. Never calculate or estimate a dollar amount yourself.
2. Cite the section number in square brackets after each claim, exactly as it appears \
in the source header — for example [Section 9.68.070]. Do not invent a code abbreviation \
or prefix that the sources do not show.
3. If the excerpts do not contain the answer, say so plainly. Do not use outside \
knowledge of housing law.
4. If a rule depends on a fact you were not given (such as the number of units on the \
property or the number of bedrooms), say which fact is needed instead of guessing.
5. Be concise — two or three sentences unless the question needs more."""
```

Rule 1 is the anti-hallucination rule that matters most in a legal-money context. A model
that adds `$13,000 + $3,000 = $16,000` has produced a figure that appears nowhere in the
law — and it looks *more* helpful than the correct answer. Rule 2 exists because models
happily invent citation prefixes (`PAMC §9.68.060`) that make an answer look verifiable
when it is not.

### The final prompt assembly

```python
# Question last — models weight the end of the message most heavily.
user_content = (
    f"Municipal code excerpts:\n\n{context}\n\n"
    f"{parcel_block}\n\n"
    f"---\n\n"
    f"Question: {question}"
)
```

Order is deliberate: bulk evidence first, the specific instruction last, where attention
concentrates.

### The parcel block

```python
def _format_parcel(parcel: dict | None) -> str:
    """Labeled block describing the selected parcel.

    States absence explicitly — if the model can't see that no parcel is selected,
    it assumes a unit count instead of asking for one.
    """
    if not parcel:
        return "Selected parcel: none (no parcel selected by the user)."

    attributes = " | ".join(f"{key}: {value}" for key, value in parcel.items())
    return f"Selected parcel (real GIS attributes):\n{attributes}"
```

The `None` branch is not defensive boilerplate — it is a correctness fix. Omit the line
entirely and the model fills the silence with an assumed unit count. Stating absence
explicitly is what makes *"which is it? I need the unit count"* the model's response.

> **IMAGE PLACEHOLDER — Figure 8**
> `docs/images/08-final-prompt.png`
> *The actual assembled prompt for the primary test case, annotated: system prompt (green),
> `[Source 1..4]` blocks (blue), parcel attribute block (orange), question (red). Truncate
> the section bodies with ellipses so the structure stays readable.*

---

## 9. The agents — role, input, output, failure mode

Four agents, hand-written as plain Python functions. **No LangChain agent framework** —
LangChain supplies loaders, splitters, embeddings, and the Chroma wrapper, but the
reasoning loop is explicit so every decision is inspectable. In a project graded on
reasoning, a hidden loop is a liability.

| Agent | Role | LLM? | Sees documents? | Can search? |
|---|---|---|---|---|
| Planner | Decide which tools are needed; rewrite the query | ✅ | ❌ | ❌ |
| Retriever-Reasoner | Call tools, judge results, retry | ✅ (labels only) | Labels only | ✅ |
| Generator | Write the grounded answer | ✅ | ✅ full text | ❌ |
| Validator | Verify claims against sources | ✅ | ✅ full text | ❌ |

Separation of powers is the point: **the agent that writes the answer cannot fetch more
evidence, and the agent that judges the answer never wrote it.**

---

### 9.1 Planner — `planner_agent.py`

**Role.** Decide *what information is needed*. It never answers the question.

**Why it needs no documents.** It is classifying, not answering. Recognising that
*"kicked out"* means eviction, and that eviction rules turn on unit count, takes language
understanding — not facts.

**The prompt:**

```python
PLANNER_PROMPT = """You are the planning step of a rental housing compliance assistant.
Your job is to decide what information is needed to answer a question. You do NOT
answer the question.

Two tools are available:

1. DOCUMENT SEARCH — semantic search over an uploaded municipal ordinance
   (rental housing rules: leases, evictions, relocation assistance, deposits).

2. PARCEL LOOKUP — attributes of one specific property, by parcel identifier.
   Available fields: {{PARCEL_FIELDS}}
   NOT available: occupancy status, rent amount, bedroom count, inspection history,
   tenant details. Those must come from the user's own question.

Guidance:
- Any question about a rule, amount, requirement, or right needs DOCUMENT SEARCH.
- PARCEL LOOKUP is needed when a rule depends on a property fact — most often the
  number of units, since several rules apply only above a unit threshold.
- Only set needs_parcel to true if a parcel is actually selected.
- search_query should be rewritten in the wording the ordinance itself would use,
  not the user's casual phrasing. Keep it short — a handful of key terms.

Reply with JSON only. No preamble, no explanation, no markdown fences.

{
  "needs_documents": true,
  "needs_parcel": false,
  "search_query": "short keyword phrase for semantic search",
  "reasoning": "one sentence on why"
}"""
```

Note the explicit **NOT available** list. Without it the planner requests occupancy status
or bedroom count — fields no public GIS dataset carries — and the reasoner then loops
searching for data that does not exist. Telling the planner the tool's *limits* is as
important as telling it the tool's capabilities.

**Two outputs that carry the weight:**

- `needs_documents` / `needs_parcel` — which tools to run.
- `search_query` — the question rewritten in the ordinance's own vocabulary.
  *"How much do I get if I'm kicked out?"* → `relocation assistance eviction without fault`.
  This is **query rewriting**, and it is what makes vector search work on casual phrasing:
  the embedding of a slang question sits far from the embedding of formal legal prose.

**Field names, not values:**

```python
the_plan = plan(
    question,
    has_apn=bool(apn),
    parcel_fields=list(parcel_attributes.keys()) if parcel_attributes else None,
)
```

The planner needs to know *what is available*, not what the values are. Sending values
wastes tokens and risks the planner reasoning about the property instead of routing.
`_fields_text()` also caps the list at 30 columns — some shapefiles carry 70+ — and
excludes geometry.

**Two guardrails:**

```python
return {
    "needs_documents": bool(data.get("needs_documents", True)),
    # Guardrail: never plan a parcel lookup when no parcel is selected, even
    # if the model said yes.
    "needs_parcel": bool(data.get("needs_parcel")) and has_apn,
    "search_query": (data.get("search_query") or question).strip(),
    "reasoning": data.get("reasoning", ""),
    "fallback": False,
}
```

`and has_apn` enforces in code what the prompt only requests. Prompts are guidance; code
is a guarantee.

**Failure mode — degrade, don't die:**

```python
def _fallback(question: str, has_apn: bool, reason: str) -> dict:
    """Safe plan used when the planner fails.

    Degrading to "try both tools" keeps the request answerable — a planner that
    raises would take down the whole query over a formatting problem.
    """
    return {
        "needs_documents": True,
        "needs_parcel": has_apn,
        "search_query": question,
        "reasoning": f"Planner unavailable ({reason}); defaulting to both tools.",
        "fallback": True,
    }
```

Malformed JSON should not cost the user their answer. The `fallback: True` flag surfaces
in the trace, so a degraded run is visible rather than silent. The only hard error is an
empty question — `PlanAgentError` → HTTP 400.

---

### 9.2 Retriever-Reasoner — `retriever_reasoner_agent.py`

**Role.** Execute the plan's tools, judge whether what came back is enough, and search
again with a better query if not. **This is the agentic loop.**

```python
MAX_RETRIES = 2   # → up to 3 attempts total

def retrieve_and_reason(question, plan, apn=None, parcel_attributes=None) -> dict:
    query = plan.get("search_query") or question

    # Once, outside the loop: a dict lookup can't return something different on
    # a second try.
    parcel = None
    if plan.get("needs_parcel"):
        parcel = get_parcel_attributes(apn, parcel_attributes)

    for attempt in range(MAX_RETRIES + 1):
        attempts = attempt + 1
        # Recorded before use, so a crash still leaves a trace of what was tried.
        queries.append(query)

        if plan.get("needs_documents"):
            result = search_sections(query)
            documents = [(d, s) for d, s in result if s > MIN_SCORE]

        findings = _summarize_findings(documents, parcel)
        verdict = check_sufficiency(question, findings)
        sufficient = verdict["sufficient"]

        if sufficient:
            break

        notes.append(verdict["missing"])

        better = verdict["better_query"]
        # No new idea, or the same query again — stop rather than burn attempts.
        if not better or better in queries:
            break

        query = better

    return {"documents": documents, "parcel": parcel, "sufficient": sufficient,
            "attempts": attempts, "queries": queries, "notes": notes}
```

**Six design decisions inside that loop:**

1. **The parcel lookup sits outside the loop.** Vector search can return something
   different for a different query; a dictionary lookup cannot. Retrying it would be pure
   waste.
2. **The sufficiency check receives labels, not full text.** It runs up to three times;
   full sections would be ~17,000 characters of tokens for a repeated yes/no question.
3. **Absence is stated explicitly.** `"Document sections found: none"` — omitting the line
   lets the model assume everything was fine, and the retry never fires.
4. **`queries.append(query)` happens before the search**, so a crash still leaves a trace
   of what was attempted.
5. **Duplicate-query guard.** If the model suggests a query already tried, stop — a model
   with no new idea will not find new evidence.
6. **A hard cap of 3.** Unbounded self-correction is how agents burn $40 in a loop. Two
   retries covers the realistic recovery case: one bad rewrite.

**The summariser:**

```python
def _summarize_findings(documents: list[tuple], parcel: dict | None) -> str:
    """Compact description of what the tools returned.

    Section labels only, not full text — this runs up to 3 times, and the full
    sections would be ~17k characters of tokens for a yes/no question.
    Absence is stated explicitly ("none") so the model can judge it.
    """
    if not documents:
        doc_summary = "Document sections found: none"
    else:
        doc_lines = ["Document sections found:"]
        for i, (doc, score) in enumerate(documents, start=1):
            meta = doc.metadata
            doc_lines.append(
                f"[Source {i}] Section {meta.get('section')} - "
                f"{meta.get('title', '')} (Score: {score:.3f})"
            )
        doc_summary = "\n".join(doc_lines)
    ...
```

**The sufficiency prompt** — the interesting part is what it forbids:

```python
SUFFICIENCY_PROMPT = """You are the retrieval-checking step of a rental housing
compliance assistant. ...

How to judge:
- Look at which ordinance sections were found and whether they cover the subject
  of the question.
- If the rule depends on a property fact (such as the number of units) and parcel
  attributes are present, treat that fact as covered.
- If the question needs a detail no dataset holds (bedroom count, rent amount,
  occupancy) and the user did not state it, that is NOT a retrieval failure —
  treat it as sufficient. The answer will ask the user for it.
- Only say sufficient: false when a needed ordinance section is genuinely absent.
- Do not demand extra sections just to be thorough. Two relevant sections are
  usually enough.

If sufficient is false, provide better_query: a short keyword phrase, worded the
way the ordinance itself would word it, aimed at the missing section. It must be
different from the query already tried.
"""
```

The third bullet took real debugging. Without it, the model treats "I don't know the
bedroom count" as a retrieval failure and loops three times searching for data no
shapefile contains. **Distinguishing "the document doesn't have it" from "the user didn't
say it" is the difference between a useful retry and a wasted one.** The fifth bullet
stops a perfectionist model from retrying forever in pursuit of completeness.

**Fails open:**

```python
try:
    raw = chat(message, max_tokens=300)
    data = extract_json(raw)
except (LLMError, ValueError, json.JSONDecodeError):
    return {"sufficient": True, "missing": "", "better_query": ""}
```

A broken *check* should not consume the retry budget. Fail-open means the loop stops and
generation proceeds with what was found.

**The string-`"false"` trap** — worth calling out, because it is a silent correctness bug:

```python
# Models sometimes return the string "false" instead of the boolean, and
# bool("false") is True — so compare explicitly.
raw_verdict = data.get("sufficient", True)
if isinstance(raw_verdict, str):
    sufficient = raw_verdict.strip().lower() not in ("false", "no", "0")
else:
    sufficient = bool(raw_verdict)
```

`bool("false") is True` in Python. A naive `bool()` cast turns every string-typed "no"
into a "yes", and the retry loop never fires. The same guard appears in the validator.

> **IMAGE PLACEHOLDER — Figure 9**
> `docs/images/09-retry-loop.png`
> *Flowchart of the retrieval loop with all four exit conditions labelled: sufficient →
> break; no `better_query` → break; duplicate query → break; attempt 3 reached → exit.
> Annotate with the real retry example from §13 ("what about the money?").*

---

### 9.3 Generator — `generator_agent.py`

**Role.** Write the answer from what was gathered. It receives documents; it never
searches. It cannot go get more evidence, which is precisely why its answer is bounded by
what was retrieved.

It extends the shared `SYSTEM_PROMPT` with parcel-specific instructions:

```python
GENERATOR_PROMPT = SYSTEM_PROMPT + """

You may also be given attributes for a specific parcel, taken from real GIS data.

How to use parcel data:
- Treat parcel attributes as verified facts. Do not second-guess them.
- Use them to decide WHICH rule applies, and state the deciding fact out loud. Name
  the attribute, its value, and the section it selects — for example: "this parcel
  has N units, so the section covering buildings above that threshold applies rather
  than the general one." Use the actual section numbers from the excerpts.
- If a rule has a numeric threshold, compare it against the parcel's actual value
  and say the result.
- If no parcel is selected, or a needed attribute is missing, say which fact you
  need instead of assuming one.

Completeness:
- When a section states payment timing, instalments, or splits, include them.
- When a section states an additional payment for particular renters (low-income,
  60 or older, disabled, a minor), mention that it may apply.
- The only arithmetic you may perform is splitting a stated total into the halves
  the ordinance itself describes. Never add, scale, or estimate a dollar amount."""
```

**"State the deciding fact out loud"** is the requirement that makes the GIS integration
*visible*. Without it the model silently picks the right section and the user cannot tell
whether parcel data was used at all. With it, the answer opens with *"Based on the parcel
data showing 30 units..."* — the join made auditable.

**The arithmetic carve-out** is the most carefully scoped rule in the system. Rule 1 of the
shared prompt says never calculate a dollar amount. But §9.68.060 states the payment is
made in two equal instalments, so reporting `$6,500 + $6,500` from a stated `$13,000` is
*reading* the ordinance, not computing beyond it. One narrow exception, stated explicitly,
in both the generator's prompt and the validator's.

**Empty-handed case — no LLM call at all:**

```python
if not documents and parcel is None:
    return {
        "answer": (
            "I don't have anything to work from — no relevant ordinance sections "
            "were found and no parcel is selected."
        ),
        "sources": [],
        "strict": strict,
    }
```

Nothing retrieved, no parcel: there is nothing to be grounded in, so calling the model
would only invite invention. Cheaper and safer to say so.

**Deliberately uncaught error:**

```python
# Deliberately not caught: if generation fails there is no answer to give, so
# let LLMError reach the router and become a 502.
answer = chat(message, max_tokens=800)
```

The planner and the checks fail open because a fallback exists. Generation has no
fallback, so its failure must be a real HTTP error — 502, signalling an upstream problem
rather than a bug in this code.

**The `strict` flag** appends `STRICT_SUFFIX`, a tighter instruction reserved for a
validator-triggered rewrite. The plumbing exists; the orchestrator does not currently
trigger a regeneration pass (see §16).

---

### 9.4 Validator — `validator_agent.py`

**Role.** Independently check whether every claim in the answer traces to a source.

**Why a separate call.** Ask a model whether its own answer was grounded and it says yes —
the answer is in its context as something it just produced and endorsed. The validator
gets a **clean context**: the answer text, the sources, no memory of writing it, and a
prompt whose only job is finding gaps.

```python
VALIDATOR_PROMPT = """You are the verification step of a rental housing compliance
assistant. You are given source material and an answer that was written from it.
Your job is to decide whether every claim in the answer is supported by those sources.
You do NOT rewrite the answer and you do NOT answer the question yourself.

A claim is SUPPORTED if:
- It appears in the municipal code excerpts, or
- It appears in the parcel attributes, or
- It follows directly from combining the two — for example "this parcel has 30 units,
  so Section 9.68.060 applies" is supported when the parcel says 30 units and the
  section states a 10-unit threshold, or
- It states that something is not addressed in the excerpts, or asks the user for a
  fact that was not provided. Those are always supported.

A claim is UNSUPPORTED if:
- A dollar amount, time period, or numeric threshold does not appear verbatim in the
  sources. A figure the answer computed by adding or scaling is unsupported even when
  the arithmetic is correct.
- It cites a section number that is not among the sources.
- It states a rule, right, or requirement that is not in the excerpts.

One exception on arithmetic: splitting a stated total into the two halves the
ordinance itself describes is supported — for example $13,000 paid as $6,500 at
notice and $6,500 at move-out.

Be precise, not suspicious. Do not flag a claim because it is paraphrased rather
than quoted. Only flag claims a careful reader could not trace to the sources.
"""
```

Four prompt decisions:

| Decision | Why |
|---|---|
| Third SUPPORTED bullet: cross-source inference is valid | Otherwise the validator flags the system's whole purpose — combining parcel + ordinance — as unsupported |
| Fourth SUPPORTED bullet: refusals and requests are supported | Otherwise the safest possible answer ("the excerpts don't address this") gets flagged as a hallucination |
| First UNSUPPORTED bullet: *"even when the arithmetic is correct"* | Anticipates the exact `$13,000 + $3,000 = $16,000` failure that actually occurred |
| *"Be precise, not suspicious"* | A validator that flags every paraphrase trains users to ignore the badge, which is worse than no badge |

**What the validator sees, and does not see:**

```python
def _format_sources(documents: list, parcel: dict | None) -> str:
    """The exact material the generator was given — full text, no scores.

    Unlike the reasoner's summary, this needs the actual sentences: the question
    here is "does this figure appear?", which a section title can't answer.
    Scores are omitted so the validator doesn't favour the top hit.
    """
```

- **Full section text**, unlike the reasoner's labels — *"does $13,000 appear?"* cannot be
  answered from a title.
- **No relevance scores** — a high score would bias it toward accepting the top hit.
- **Parcel attributes, labelled as real GIS data** — otherwise it flags *"this parcel has
  30 units"* as an unsupported claim.
- **Answer placed last** in the message, where attention concentrates. It is the thing
  being judged.

**Fails open, but honestly:**

```python
try:
    raw = chat(message, max_tokens=500)
    data = extract_json(raw)
except (LLMError, ValueError, json.JSONDecodeError):
    return {"supported": True, "unsupported_claims": [], "checked": False}
```

`checked: False` is the important field. The UI shows **no badge at all** in that case —
never a green tick that cannot be backed up. Failing open on the verdict while being
honest about the check is the only defensible combination: a false warning erodes trust
in every future badge, and a false tick is worse.

**The list wins over the verdict:**

```python
return {
    # A claim list and a "supported" verdict can disagree — trust the list.
    "supported": supported and not claims,
    "unsupported_claims": claims,
    "checked": True,
}
```

Models return `supported: true` alongside a populated `unsupported_claims` list more often
than you would hope. The specific findings are more reliable than the summary verdict, so
the list decides.

**Evidence that it works.** Running the primary test case on a weaker model produced
*"for a total of $16,000"* — a figure that appears nowhere in the ordinance, arrived at by
adding $13,000 + $3,000. The validator caught it and flagged it in the UI.

> **IMAGE PLACEHOLDER — Figure 10**
> `docs/images/10-validator-catch.png`
> *The `⚠ 1 unsupported` badge with the claim list expanded, showing the caught
> `$16,000` fabrication. Ideally the same question beside it showing `✓ verified` on the
> stronger model. This is the report's proof that verification is real and not decorative.*

---

## 10. Validation states and what each one means

The API returns a `validation` object with three fields. Four distinct outcomes are
possible, and the UI renders each differently.

```json
"validation": {
  "supported": true,
  "unsupported_claims": [],
  "checked": true
}
```

| State | `checked` | `supported` | `unsupported_claims` | UI | Meaning |
|---|---|---|---|---|---|
| **A — Verified** | `true` | `true` | `[]` | `✓ verified` (green) | The validator ran and traced every claim to a retrieved section or a parcel attribute. |
| **B — Unsupported claims found** | `true` | `false` | `["…", "…"]` | `⚠ N unsupported` (amber) + bulleted claim list | The validator ran and found at least one claim it could not trace. **The answer is still shown** — flagged, not hidden, so the user can judge. |
| **C — Not checked** | `false` | `true` | `[]` | **no badge at all** | The validator itself failed (network error, unparseable JSON) or the answer was empty. Fail-open on the verdict, honest about the gap. Absence of a badge means "unverified", never "verified". |
| **D — Nothing to answer from** | `true` | `true` | `[]` | no sources, no meaningful badge | The generator short-circuited: no sections passed the score floor and no parcel was selected. The answer text says so plainly. No LLM call was made. |

The UI enforces state C:

```jsx
{/* Only shown when the validator actually ran — never claim a verdict
    we don't have. */}
{validation?.checked && <ValidationBadge validation={validation} />}
```

```jsx
function ValidationBadge({ validation }) {
  const { supported, unsupported_claims: claims = [] } = validation;

  if (supported) {
    return (
      <span className="source-chip badge-ok" title="Every claim traced to a source">
        ✓ verified
      </span>
    );
  }

  return (
    <span className="source-chip badge-warn"
          title={claims.join(" · ") || "Unsupported claims found"}>
      ⚠ {claims.length || "unverified"} unsupported
    </span>
  );
}
```

### The separate axis: *sufficient*

**`validation.supported` and `trace.sufficient` answer different questions and must not
be confused.**

| Field | Question it answers | Set by | Where it shows |
|---|---|---|---|
| `trace.sufficient` | *Did we find enough evidence?* | Retriever-Reasoner (before generation) | Trace summary: `3 searches · insufficient` |
| `validation.supported` | *Does the answer stick to the evidence we found?* | Validator (after generation) | Badge: `✓ verified` |

They combine into four meaningful situations:

| `sufficient` | `supported` | Interpretation |
|---|---|---|
| ✅ | ✅ | **The good case.** Found enough, stayed within it. |
| ❌ | ✅ | **Honest limitation.** Retrieval came up short after up to 3 tries, and the answer correctly says so or asks for the missing fact. Trustworthy but incomplete — a *good* outcome, not a failure. |
| ✅ | ❌ | **Hallucination caught.** Evidence was there; the answer went beyond it. This is exactly what the validator exists for. |
| ❌ | ❌ | **Worst case.** Thin evidence *and* the answer overreached. The user sees both signals and should not rely on the answer. |

> **IMAGE PLACEHOLDER — Figure 11**
> `docs/images/11-validation-states.png`
> *Four stacked chat-bubble screenshots, one per state A–D, each with the badge (or its
> absence) circled and a one-line caption. Include a 2×2 matrix graphic for the
> sufficient × supported combinations.*

---

## 11. The reasoning trace

The trace is the visible evidence of agentic behaviour. Without it, "the system reasons
about its own retrieval" is an unfalsifiable claim.

```json
"trace": {
  "plan": {
    "needs_documents": true,
    "needs_parcel": true,
    "search_query": "relocation assistance eviction without fault",
    "reasoning": "The amount owed depends on the number of units, so both the
                  ordinance and the parcel's unit count are needed.",
    "fallback": false
  },
  "sufficient": true,
  "attempts": 1,
  "queries": ["relocation assistance eviction without fault"],
  "notes": []
}
```

| Field | Meaning | What it reveals |
|---|---|---|
| `plan.reasoning` | The planner's one-sentence justification | Why these tools |
| `plan.needs_documents` / `needs_parcel` | Tools selected | Rendered as `documents + parcel` |
| `plan.search_query` | The rewritten query | **Query rewriting made visible** — compare it to what the user typed |
| `plan.fallback` | `true` if the planner failed and defaulted | A degraded run is never silent |
| `sufficient` | Final verdict of the last sufficiency check | Whether retrieval was ever judged adequate |
| `attempts` | 1, 2, or 3 | **`> 1` means the self-correction loop fired** |
| `queries` | Every query tried, in order | The refinement path: `"what about the money?"` → `"relocation assistance payment amount"` |
| `notes` | Each `missing` explanation from a failed check | *Why* the reasoner rejected an attempt |

Rendered as a collapsible `<details>` element — present for anyone who wants it, out of
the way for anyone who does not:

```jsx
{/* The reasoning trace is the visible evidence of agentic behavior. */}
{trace && (
  <details className="trace">
    <summary>
      {trace.attempts} search{trace.attempts > 1 ? "es" : ""}
      {trace.sufficient ? "" : " · insufficient"}
    </summary>
    <div className="trace-body">
      <div><strong>Plan:</strong> {trace.plan?.reasoning}</div>
      <div><strong>Tools:</strong>{" "}
        {[trace.plan?.needs_documents && "documents",
          trace.plan?.needs_parcel && "parcel"].filter(Boolean).join(" + ") || "none"}
      </div>
      <div><strong>Queries:</strong> {trace.queries?.join(" → ")}</div>
      {trace.notes?.length > 0 && (
        <div><strong>Missing:</strong> {trace.notes.join("; ")}</div>
      )}
    </div>
  </details>
)}
```

The summary line is the at-a-glance signal: `1 search` = clean first hit;
`3 searches · insufficient` = the loop tried everything and is telling you so.

> **IMAGE PLACEHOLDER — Figure 12**
> `docs/images/12-trace-expanded.png`
> *Two screenshots side by side: (left) `1 search` collapsed and expanded on a clean run;
> (right) `3 searches · insufficient` expanded, showing the query refinement chain and the
> `Missing:` notes. The right-hand one is the money shot for "this is agentic".*

---

## 12. Plain RAG vs Agentic RAG — the measured difference

The plain-RAG baseline is kept in the codebase deliberately, so the same question can be
run down both paths and the difference demonstrated rather than asserted.

```python
def answer_question(question: str, k: int = 4) -> dict:
    """Retrieve relevant sections and answer the question from them."""
    if not question or not question.strip():
        raise RAGError("Question cannot be empty.")

    results = search_sections(question, k)
    filtered = [(doc, score) for doc, score in results if score > MIN_SCORE]

    # Nothing relevant — don't spend an LLM call inventing an answer.
    if not filtered:
        return {"answer": "I couldn't find anything relevant in the uploaded documents. "
                          "Try rephrasing, or check that the right document is indexed.",
                "sources": [], "retrieved": len(results)}

    context = build_context(filtered)
    ...
    answer = chat(message)
```

| | Plain RAG (`rag.py`) | Agentic RAG (`agents/`) |
|---|---|---|
| Query used | The user's raw words | Rewritten into ordinance vocabulary |
| Tools | Vector search only | Vector search **+** parcel lookup, chosen per question |
| Retrieval attempts | Exactly 1 | 1–3, driven by a self-assessment |
| Knows if retrieval was bad | No | Yes — `check_sufficiency` |
| Parcel-dependent answers | No | Yes |
| Answer verified | No | Yes — independent validator pass |
| LLM calls | 1 | 4–6 |
| Latency | ~2 s | ~6–10 s |

**The four agentic behaviours, and where each lives:**

| Behaviour | Agent | Mechanism |
|---|---|---|
| **Tool selection** | Planner | `needs_documents` / `needs_parcel` |
| **Query rewriting** | Planner | `search_query` |
| **Self-assessment + retry** | Retriever-Reasoner | `check_sufficiency` → `better_query`, up to 2 retries |
| **Output verification** | Validator | Independent claim-by-claim check |

The distinction is not "more LLM calls". It is that **the system evaluates its own work
and changes its behaviour based on the result.** Plain RAG retrieves once and answers
regardless of whether what it retrieved was any good.

---

## 13. Test cases and results

### 13.1 Primary case — the parcel-dependent answer

**Setup.** APN `127-53-008` (`UNITS: 30`).
**Question.** *"If a tenant with a 2-bedroom unit here is evicted without fault, how much
relocation assistance is owed?"*

**Answer.**

> Based on the parcel data showing **30 units**, Section 9.68.060 applies rather than
> Section 9.68.050, because this section governs structures with 10 or more residential
> rental units. For a 2-bedroom unit, relocation assistance is **$13,000**. This amount is
> paid in two instalments: one half ($6,500) at notice, the remainder ($6,500) when the
> renter vacates. If occupied by a low-income household, a renter 60 or older, a disabled
> renter, or a minor, an **additional $3,000** applies.

**Result.** `1 search` · `✓ verified`. Every figure verbatim from the ordinance; the
section choice driven by real GIS data; the deciding fact stated out loud.

### 13.2 Inverse case — the proof

Clicking a **single-family** parcel and asking the identical question returns Section
**9.68.050** — one month's rent — *because* the parcel falls under the 10-unit threshold.

**13.1 and 13.2 together are the demonstration.** Same question, different parcel,
different legally-correct answer. No document-only chatbot can produce this pair.

> **IMAGE PLACEHOLDER — Figure 13**
> `docs/images/13-primary-and-inverse.png`
> *Two full-width screenshots stacked: the 30-unit answer with §9.68.060 chips, and the
> single-family answer with §9.68.050 chips. Include the map showing which parcel is
> selected in each. If only one figure survives the page budget, keep this one.*

### 13.3 Guardrails

| Question | Outcome | Which control fired |
|---|---|---|
| *"How many parking spaces are required per unit?"* | Refused — no number invented | `MIN_SCORE` floor + prompt rule 3 |
| *"What's the rent control limit in San Francisco?"* | Refused — outside the indexed document | Prompt rule 3 (no outside knowledge) |
| *"what about the money?"* | Retry loop fired, then asked which payment was meant | `check_sufficiency` → `better_query` |
| Threshold question with **no parcel selected** | Asked for the unit count instead of assuming | `_format_parcel(None)` + prompt rule 4 |
| Empty question | HTTP 400 | Pydantic + `PlanAgentError` |
| `..\..\app\config.py` as upload filename | Written as `config.py` inside the upload dir, then rejected on extension | `Path(...).name` + `ALLOWED_SUFFIXES` |

### 13.4 Model tier mattered more than prompt tuning

Running the primary case on `claude-3-haiku` produced the correct dollar figure but broke
three prompt rules simultaneously: it never mentioned the unit count, omitted the payment
split, and computed a `$16,000` total. Switching to `claude-sonnet-4.5` fixed all three
**with no prompt change**.

**Lesson worth recording:** when a grounded-generation system breaks rules, check the model
tier before rewriting prompts. The generator prompt carries ~10 simultaneous constraints,
which is past what a small model reliably holds. The validator caught the `$16,000` on the
weaker model — the safety net worked exactly as designed.

### 13.5 Generalisation — ingestion across three cities

| City | Heading format | Result |
|---|---|---|
| Palo Alto | `9.68.060   Purpose.` | ✅ 9 sections, 37 chunks |
| San Joaquin | `§ 150.060  APPLICABILITY.` | ✅ 6 sections, 12 chunks |
| Los Angeles | `SEC. 45.83. RENTAL HOUSING.` | ❌ no regex match → size-based fallback |

San Joaquin only worked after the regex was broadened to accept `§` prefixes and two-part
numbers. **Los Angeles still fails** — uppercase `SEC.` followed by a period and a single
space. Documented rather than hidden, because it identifies the exact next feature (§17).

San Joaquin also revealed something more interesting: its ordinance is *Rental Housing
Standards* — habitability and inspection, with **no dollar amounts and no unit
thresholds**. The two-tool architecture pays off specifically for ordinances with
**property-dependent thresholds**. That is a finding about where the design applies, not a
bug in it.

> **IMAGE PLACEHOLDER — Figure 14**
> `docs/images/14-three-cities.png`
> *Three heading samples side by side (cropped from the actual PDFs) with the regex
> match/no-match annotated on each. Makes the generalisation limit concrete in one glance.*

---

## 14. Reliability and safety controls

| Control | Where | Failure it prevents |
|---|---|---|
| Score floor `MIN_SCORE = 0.15` | `rag.py`, reasoner | Irrelevant sections entering the prompt and inviting invention |
| Empty-context short-circuit | `generator_agent` | An LLM call with nothing to be grounded in |
| Retry cap `MAX_RETRIES = 2` | reasoner | Unbounded self-correction loops and runaway cost |
| Duplicate-query guard | reasoner | Re-running an identical search |
| Fail-open sufficiency check | reasoner | A broken *check* consuming the retry budget |
| Fail-open validator with `checked: False` | validator | A green tick that cannot be backed up |
| Claim-list-over-verdict | validator | `supported: true` alongside a populated claim list |
| Explicit string-`"false"` handling | reasoner + validator | `bool("false") is True` silently disabling both checks |
| Planner fallback plan | planner | One malformed JSON reply killing the whole request |
| `needs_parcel and has_apn` | planner | Planning a lookup that cannot succeed |
| `temperature = 0.0` | LLM client | Non-repeatable legal answers |
| `Path(...).name` on upload | upload router | Path traversal via a client-supplied filename |
| Extension check before write | upload router | Rejected files persisting on disk |
| Delete file on failed ingestion | upload router | Orphaned, un-indexed uploads |
| Pydantic `min_length=1, max_length=2000` | query router | Empty and abusive payloads |
| Typed HTTP mapping (400 / 502 / 500) | query router | An upstream model outage looking like a server bug |
| Geometry excluded from prompts | parcel store, planner | Thousands of coordinate characters wasting the context |
| Parcel attributes never stored server-side | parcel store | One user seeing another user's selected parcel |
| Stable chunk IDs | chroma client | Duplicate results after re-upload |

Two patterns recur and are worth naming:

**Fail open on judgment, fail closed on generation.** The planner and both checks degrade
gracefully because a sensible default exists. Generation has no fallback, so its failure
becomes an honest 502.

**Enforce in code what the prompt requests.** `needs_parcel and has_apn`, the score floor,
the retry cap, and the claim-list-wins rule are all code guarantees over prompt guidance.
Prompts are persuasion; code is enforcement.

---

## 15. Deployment

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

**Why two workflows.** CI answers *"does the code work?"* and runs on every push and PR.
Deploy answers *"ship it"* and runs only on `main`. A CI failure means broken code; a
deploy failure means production may be half-updated. Different problems, different
urgency.

### Startup command

```
gunicorn -w 1 -k uvicorn.workers.UvicornWorker --timeout 600 --bind 0.0.0.0:8000 app.main:app
```

| Flag | Why |
|---|---|
| `-w 1` | Each worker loads its own copy of the embedding model — memory scales linearly with worker count |
| `-k uvicorn.workers.UvicornWorker` | FastAPI is ASGI; gunicorn speaks WSGI by default |
| `--timeout 600` | PyTorch import takes ~51 s; the default 30 s kills the worker mid-import, forever |

### App settings

| Setting | Purpose |
|---|---|
| `SCM_DO_BUILD_DURING_DEPLOYMENT=1` | Azure runs `pip install` on the instance, so wheels match the server platform and the upload stays ~200 KB |
| `DATA_DIR=/home/data` | Only `/home` survives a restart on App Service Linux |
| `HF_HOME=/home/.cache/huggingface` | Caches the embedding model so it downloads once, not per cold start |
| `ALLOWED_ORIGINS` | The deployed frontend's URL — a hardcoded localhost origin blocks every real request |
| `WEBSITES_CONTAINER_START_TIME_LIMIT=1800` | The default 230 s is shorter than a cold PyTorch start |

### Three deployment problems worth recording

1. **sqlite3 too old.** Azure's Linux image ships sqlite3 < 3.35; Chroma raises a
   `RuntimeError` at import. Fixed with `pysqlite3-binary` (Linux-only marker — there are
   no Windows wheels) plus a `sys.modules` swap in `app/__init__.py`, which must remain the
   first thing imported. A pure *system-library* mismatch, invisible locally because Python
   on Windows bundles a newer sqlite3.

2. **CUDA PyTorch.** The default PyPI `torch` wheel bundles CUDA (~2.5 GB) for a GPU that
   App Service does not have. Pinning the `+cpu` build from PyTorch's own index cuts it to
   ~200 MB.

3. **Green ≠ running.** `azure/webapps-deploy` uploads and finishes; Azure installs and
   starts afterwards. A green pipeline with a 503 site is expected, not a contradiction.
   Verification means hitting `/health`, not reading the pipeline.

### Known pipeline weakness

`ci.yml` and `deploy.yml` both trigger on push to `main` and run **concurrently**, so a
deploy can proceed even if CI fails. In a team the fix is requiring CI as a PR status check
so `main` is verified before merge; for direct pushes it would be one workflow with
`needs:`.

> **IMAGE PLACEHOLDER — Figure 15**
> `docs/images/15-deployment.png`
> *GitHub Actions run summary (both workflows green) plus the Azure portal showing the App
> Service and Static Web App. Optionally the `/health` response and the live `/docs` page.*

---

## 16. Known limitations

**Ingestion**
- `document_loader` implements **PDF only**. The router advertises `.txt`, `.md`, `.csv`,
  `.xlsx`, `.xls`; those uploads pass the extension check and then fail at load with a 400.
  The dispatch structure exists; the branches are not wired.
- Section chunking assumes numbered headings. Unrecognised numbering falls back to
  size-based chunking — searchable, but without the guarantee that a rule stays with its
  exemptions. Los Angeles-style `SEC. 45.83.` headings currently fall back.
- Scanned PDFs with no text layer are rejected. No OCR path.

**Retrieval**
- No re-ranking model — raw embedding similarity only.
- All documents share one Chroma collection and `/query` exposes no per-document filter.
  Indexing two cities at once can mix sources in one answer. The metadata and the
  `source_file` filter parameter both exist; only the API plumbing is missing.
- The 4-section context cap is fixed.

**Reasoning**
- Sufficiency and validation are themselves LLM calls, so they inherit the base model's
  reliability. Mitigation, not a guarantee.
- The validator flags but does not trigger a rewrite. `STRICT_SUFFIX` and the `strict`
  flag exist in the generator; the orchestrator does not yet call generation a second time.
- 4–6 LLM calls per question → ~6–10 s latency.

**Data**
- Public parcel datasets carry no occupancy status, rent registry status, inspection
  history, or bedroom count — those are internal housing-department records. Bedroom count
  must come from the user's question.
- Validated end to end on one city. Architecturally city-agnostic; empirically proven on
  Palo Alto.

**Operations**
- No authentication and no per-user document isolation. Acceptable for a demo, not for
  production.
- Uploaded documents and the vector store live on App Service's `/home`; a redeploy may
  clear them, requiring re-upload.
- On the free tier the app sleeps when idle, so the first request after a pause pays the
  full model-load cold start.

**Product**
- Answers are informational, not legal advice. A production version needs prominent
  disclaimers and a link to the city's own code.
- Ordinances are amended regularly; a stale index can be confidently wrong. Answers should
  carry a "last indexed" date.

**Frontend**
- The Find-parcel widget uses Esri's address geocoder, so it searches addresses, not APNs.
  Searching by parcel ID needs a layer source built from the detected ID field.

---

## 17. Roadmap

The goal: **any city, not just Palo Alto.** Upload an ordinance and a parcel layer, and it
works. The obstacles below come from actual testing, not speculation.

### Next four features, in priority order

**1. Structure-inference agent** *(highest value)*

Replace the hardcoded chunking regex with an LLM call that reads the first 2–3 pages and
returns the document's own structure:

```json
{
  "has_sections": true,
  "heading_example": "SEC. 45.83. RENTAL HOUSING.",
  "regex": "^SEC\\.\\s+(\\d+\\.\\d+)\\.\\s+(.+)$",
  "citation_prefix": "LAMC"
}
```

One call per document, at upload. Fixes the Los Angeles failure **and** removes the
hardcoded citation prefix in the same step.

**2. Complete the loader branches.** Wire TXT / MD / CSV / Excel so the router's advertised
extensions all work, closing the gap noted in §16.

**3. Per-document filtering in `/query`.** `search_sections` already accepts `source_file`
and every chunk carries the metadata. Exposing it through the API plus a document picker
makes multi-city correct rather than merely possible.

**4. Parcel schema-mapping agent.** Show the LLM the shapefile's column names and one
sample row; ask which field is the parcel ID, the unit count, the zoning. Any county's
schema then works, replacing the current `APN|PARCELID|PIN|AIN` pattern.

### What genuinely blocks nationwide scale

| Obstacle | Nature |
|---|---|
| **Document acquisition** | ~19,000 US municipalities; codes sit behind Municode, American Legal Publishing, eCode360, each with its own terms. A licensing and data problem, not an AI one. |
| **Parcel data** | County-level, ~3,000 counties, inconsistent schemas, some paid. No free, current, national dataset. |
| **Applicability** | Only ~200 US cities have rent stabilisation, mostly CA/NY/NJ/OR/MD. Habitability codes are universal but rarely threshold-driven, so the GIS join matters less there. |
| **Freshness** | Ordinances amend continuously; a stale index is confidently wrong. |
| **Liability** | Telling a tenant they are owed $13,000 approaches legal advice. Shapes the product; not a technical blocker. |

### The defensible claim

Not "RAG over PDFs" — that is commodity. The differentiator is **joining unstructured
legal text to structured property data so that the answer depends on the specific
parcel**, with a verification pass that says out loud when it cannot back a claim up.

---

## 18. Assignment task mapping

| # | Requirement | Where it is satisfied |
|---|---|---|
| 1 | Project foundation | Repo layout, `.env.example`, `config.py`, layered `app/` package |
| 2 | User interaction layer | React shell — icon rail, drawer panels, Esri map, chat panel |
| 3 | Document ingestion | `ingestion/document_loader.py` (PDF implemented; other branches noted in §16) |
| 4 | Data prepared for semantic search | `ingestion/chunker.py` — section-aware split, TOC removal, size enforcement, fallback |
| 5 | Vector-based knowledge store | `vectorstore/embeddings.py`, `chroma_client.py` — local 384-dim embeddings, persisted Chroma, stable IDs |
| 6 | Intelligent document retrieval | `search_sections` — over-fetch `k*4`, dedup by section, reassemble split sections, score floor |
| 7 | RAG pipeline | `rag.py` (plain baseline, kept for comparison) and `generator_agent.py` (agent path) |
| 8 | Agent-based reasoning using available tools | Four agents; **two heterogeneous tools** — semantic vector search and structured parcel lookup — selected per question by the planner |
| 9 | Reliability and safety controls | §14 — 20 controls: validator, score floor, retry caps, fail-open judgment, typed errors, path-traversal guard |
| 10 | Deploy and document | Azure App Service + Static Web Apps, GitHub Actions CI/CD, this report |

**On task 8 specifically.** The assignment says agents use "available tools" — plural and
open-ended. The GIS parcel tool is one tool alongside document search, not a substitute for
it. Document upload and Q&A work independently: with no map interaction at all, the system
still satisfies tasks 1–10 from document Q&A alone. **The GIS integration is additive** —
it is what makes the answers parcel-specific, and it is the project's differentiator, but
the core requirements do not depend on it.

---

## 19. Appendix — API reference

### `POST /api/upload_document`

`multipart/form-data`, field name `file`.

```json
{
  "filename": "Palo_Alto_9.68.pdf",
  "pages": 7,
  "chunks": 37,
  "sections": ["9.68.010", "9.68.020", "9.68.030", "9.68.040",
               "9.68.050", "9.68.060", "9.68.070", "9.68.080", "9.68.090"],
  "message": "Indexed 37 chunks from Palo_Alto_9.68.pdf."
}
```

| Status | Cause |
|---|---|
| 400 | No filename · unsupported extension · empty file · no text layer (needs OCR) |
| 500 | Ingestion failure (embedding, storage) |

### `POST /api/query`

```json
{
  "question": "If a tenant with a 2-bedroom unit here is evicted without fault, how much relocation assistance is owed?",
  "apn": "127-53-008",
  "parcel_attributes": { "APN": "127-53-008", "UNITS": 30, "ZONEGIS": "RM-40" }
}
```

Response:

```json
{
  "answer": "Based on the parcel data showing 30 units, Section 9.68.060 applies …",
  "sources": [
    { "section": "9.68.060", "title": "Relocation assistance",
      "source_file": "Palo_Alto_9.68.pdf", "score": 0.612 },
    { "section": "9.68.050", "title": "Notice requirements",
      "source_file": "Palo_Alto_9.68.pdf", "score": 0.431 }
  ],
  "parcel": { "APN": "127-53-008", "UNITS": 30, "ZONEGIS": "RM-40" },
  "validation": { "supported": true, "unsupported_claims": [], "checked": true },
  "trace": {
    "plan": { "needs_documents": true, "needs_parcel": true,
              "search_query": "relocation assistance eviction without fault",
              "reasoning": "…", "fallback": false },
    "sufficient": true, "attempts": 1,
    "queries": ["relocation assistance eviction without fault"], "notes": []
  }
}
```

| Status | Cause |
|---|---|
| 400 | Empty question (`PlanAgentError`) |
| 422 | Pydantic validation — question outside 1–2000 characters |
| 502 | `LLMError` — OpenRouter unreachable, non-200, or unusable response shape |
| 500 | Anything else |

### `GET /health`

Liveness probe. The correct way to verify a deployment — a green pipeline only means the
upload finished.

> **IMAGE PLACEHOLDER — Figure 16**
> `docs/images/16-swagger.png`
> *FastAPI's auto-generated `/docs` page with both endpoints expanded, and one executed
> `/api/query` showing the real JSON response including `validation` and `trace`.*

---

## 20. Appendix — Running locally

```powershell
# Backend
cd backend
python -m venv ..\venv
..\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env        # then add your OPENROUTER_API_KEY
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, upload an ordinance PDF via the Documents drawer, upload a
parcel shapefile `.zip` via Add data, click a parcel on the map, and ask a question.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | Auth for the chat LLM |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-4.5` | Swap models without a code change |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embeddings |
| `COLLECTION_NAME` | `ordinances` | Chroma collection |
| `DATA_DIR` | `backend/data` | Set to `/home/data` on Azure |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS |

---

## Image checklist

| # | File | Subject |
|---|---|---|
| 1 | `01-hero-two-answers.png` | Same question, two parcels, two answers |
| 2 | `02-full-ui.png` | Full application window, annotated |
| 3 | `03-architecture.png` | Redrawn architecture diagram |
| 4 | `04-upload-result.png` | Upload result: pages / chunks / sections |
| 5 | `05-query-sequence.png` | Query sequence diagram with the retry loop |
| 6 | `06-chunking.png` | Raw PDF → 9 sections → §9.68.060 in 7 parts |
| 7 | `07-search-sections.png` | Over-fetch → dedup → stitch funnel |
| 8 | `08-final-prompt.png` | The assembled prompt, colour-annotated |
| 9 | `09-retry-loop.png` | Retrieval loop flowchart, 4 exit conditions |
| 10 | `10-validator-catch.png` | The `$16,000` fabrication flagged |
| 11 | `11-validation-states.png` | States A–D + the sufficient × supported matrix |
| 12 | `12-trace-expanded.png` | `1 search` vs `3 searches · insufficient` |
| 13 | `13-primary-and-inverse.png` | Primary + inverse case, with the map |
| 14 | `14-three-cities.png` | Three heading formats, regex match annotated |
| 15 | `15-deployment.png` | Actions green + Azure portal + `/health` |
| 16 | `16-swagger.png` | `/docs` with a live `/api/query` response |

**Must-have four, if the page budget is tight:** Figures 1, 6, 7, 12.

---

*Exon Rental — parcel-aware housing compliance. Answers are informational, not legal advice.*
