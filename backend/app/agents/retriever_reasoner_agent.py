import json

from app.agents.json_utils import extract_json
from app.llm.openrouter_client import LLMError, chat
from app.vectorstore.chroma_client import search_sections
from app.parcel_data.parcel_store import get_parcel_attributes
from app.rag import MIN_SCORE

SUFFICIENCY_PROMPT = """You are the retrieval-checking step of a rental housing
compliance assistant. You are given a question and a summary of what was found.
Your job is to judge whether the findings are enough to answer the question.
You do NOT answer the question yourself.

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

Reply with JSON only. No preamble, no explanation, no markdown fences.

{
  "sufficient": true,
  "missing": "what is absent, or empty string if sufficient",
  "better_query": "new search phrase, or empty string if sufficient"
}"""

MAX_RETRIES = 2

def _summarize_findings(documents: list[tuple], parcel: dict | None) -> str:
    """Compact description of what the tools returned.

    Section labels only, not full text — this runs up to 3 times, and the full
    sections would be ~17k characters of tokens for a yes/no question.
    Absence is stated explicitly ("none") so the model can judge it.
    """
    # 1. Format the retrieved sections
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

    # 2. Format parcel attributes on a single line
    if parcel:
        # Converts dictionary items to a clean 'key: value, key: value' single line
        parcel_str = ", ".join(f"{k}: {v}" for k, v in parcel.items())
        parcel_summary = f"Parcel Attributes: {parcel_str}"
    else:
        parcel_summary = "Parcel Attributes: none"

    # 3. Combine both text blocks
    return f"{doc_summary}\n\n{parcel_summary}"


def check_sufficiency(question: str, findings: str) -> dict:
    """Ask the LLM whether the findings cover the question.

    Fails OPEN — if the call or the JSON parse breaks, report sufficient so the
    loop stops. A formatting hiccup should not trigger extra searches.
    """
    message = [
        {"role": "system", "content": SUFFICIENCY_PROMPT},
        {
            "role": "user",
            "content": f"Question: {question}\n\nWhat was found:\n{findings}",
        },
    ]

    try:
        raw = chat(message, max_tokens=300)
        data = extract_json(raw)
    except (LLMError, ValueError, json.JSONDecodeError):
        return {"sufficient": True, "missing": "", "better_query": ""}

    # Models sometimes return the string "false" instead of the boolean, and
    # bool("false") is True — so compare explicitly.
    raw_verdict = data.get("sufficient", True)
    if isinstance(raw_verdict, str):
        sufficient = raw_verdict.strip().lower() not in ("false", "no", "0")
    else:
        sufficient = bool(raw_verdict)

    return {
        "sufficient": sufficient,
        "missing": str(data.get("missing") or "").strip(),
        "better_query": str(data.get("better_query") or "").strip(),
    }


def retrieve_and_reason(
    question: str,
    plan: dict,
    apn: str | None = None,
    parcel_attributes: dict | None = None,
) -> dict:

    """Call the tools, judge the results, retry document search if lacking.

    Returns whatever the last attempt produced even when it gives up — a partial
    answer with a caveat beats no answer.
    """
    if not plan:
        raise ValueError("retrieve_and_reason requires a plan from the planner agent.")

    documents = []
    queries = []
    notes = []
    sufficient = True
    attempts = 0

    # The planner rewrites the question into ordinance wording; fall back to the
    # raw question if it didn't.
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

    return {
        "documents": documents,
        "parcel": parcel,
        "sufficient": sufficient,
        "attempts": attempts,
        "queries": queries,
        "notes": notes,
    }


