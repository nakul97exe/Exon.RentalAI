"""Validator agent — checks the generated answer against its sources.

Runs once, after generation. Flags unsupported claims; it does not regenerate.
A fresh LLM call with no memory of writing the answer, so it has no reason to
defend it.
"""
import json

from app.agents.json_utils import extract_json
from app.llm.openrouter_client import LLMError, chat

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

Reply with JSON only. No preamble, no explanation, no markdown fences.

{
  "supported": true,
  "unsupported_claims": ["short description of each unsupported claim, or empty list"]
}"""


def _format_sources(documents: list, parcel: dict | None) -> str:
    """The exact material the generator was given — full text, no scores.

    Unlike the reasoner's summary, this needs the actual sentences: the question
    here is "does this figure appear?", which a section title can't answer.
    Scores are omitted so the validator doesn't favour the top hit.
    """
    if not documents:
        doc_summary = "Municipal code excerpts: none"
    else:
        blocks = []
        for i, (doc, _score) in enumerate(documents, start=1):
            meta = doc.metadata
            blocks.append(
                f"[Source {i}] Section {meta.get('section')} - {meta.get('title', '')}\n"
                f"{doc.page_content}"
            )
        doc_summary = "\n\n---\n\n".join(blocks)

    if parcel:
        attributes = " | ".join(f"{key}: {value}" for key, value in parcel.items())
        parcel_summary = f"Parcel attributes (real GIS data): {attributes}"
    else:
        parcel_summary = "Parcel attributes: none"

    return f"{doc_summary}\n\n{parcel_summary}"


def validate(
    question: str,
    answer: str,
    documents: list[tuple],
    parcel: dict | None = None,
) -> dict:
    """Check whether the answer's claims are supported by the sources.

    Fails OPEN — if the call or parse breaks, report supported with checked=False
    so the UI shows no verdict rather than a false warning.
    """
    if not answer or not answer.strip():
        return {"supported": True, "unsupported_claims": [], "checked": False}

    sources = _format_sources(documents, parcel)

    # Answer last — models weight the end of the message most heavily, and the
    # answer is what's being judged.
    user_content = (
        f"Sources:\n\n{sources}\n\n"
        f"---\n\n"
        f"Question that was asked: {question}\n\n"
        f"Answer to check:\n{answer}"
    )

    message = [
        {"role": "system", "content": VALIDATOR_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        raw = chat(message, max_tokens=500)
        data = extract_json(raw)
    except (LLMError, ValueError, json.JSONDecodeError):
        return {"supported": True, "unsupported_claims": [], "checked": False}

    # Models sometimes return the string "false", and bool("false") is True.
    raw_verdict = data.get("supported", True)
    if isinstance(raw_verdict, str):
        supported = raw_verdict.strip().lower() not in ("false", "no", "0")
    else:
        supported = bool(raw_verdict)

    claims = data.get("unsupported_claims") or []
    if isinstance(claims, str):
        claims = [claims]
    claims = [str(c).strip() for c in claims if str(c).strip()]

    return {
        # A claim list and a "supported" verdict can disagree — trust the list.
        "supported": supported and not claims,
        "unsupported_claims": claims,
        "checked": True,
    }
