"""Planner agent — decides which tools are needed to answer a question.

Runs once per question, no loop. Outputs a plan; the orchestrator executes it.
"""
import json

from app.llm.openrouter_client import LLMError, chat
from app.agents.json_utils import extract_json

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


class PlanAgentError(Exception):
    """Raised when the question is unusable."""


# Used when no parcel is selected, so the planner still knows roughly what a parcel
# dataset offers without being told a specific city's column names.
_GENERIC_FIELDS = (
    "typical parcel attributes such as number of residential units, zoning code, "
    "land use, year built, lot size, and building size"
)

# Geometry columns are huge and useless to the planner.
_EXCLUDED_FIELDS = {"Geometry", "GeometryJsonb", "geometry", "SHAPE"}


def _fields_text(parcel_fields: list[str] | None) -> str:
    """Describe the parcel columns actually present in the uploaded data.

    Keeps the prompt honest for any city — a dataset calling unit count NUM_UNITS
    shouldn't be described to the planner as UNITS.
    """
    if not parcel_fields:
        return _GENERIC_FIELDS

    usable = [f for f in parcel_fields if f not in _EXCLUDED_FIELDS]
    if not usable:
        return _GENERIC_FIELDS

    # Cap the list — some shapefiles carry 70+ columns and the planner only needs
    # to know roughly what is available.
    shown = usable[:30]
    suffix = f", and {len(usable) - len(shown)} more" if len(usable) > len(shown) else ""
    return ", ".join(shown) + suffix


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


def plan(
    question: str,
    has_apn: bool,
    parcel_fields: list[str] | None = None,
) -> dict:
    """Decide which tools are needed and rewrite the search query."""
    if not question or not question.strip():
        raise PlanAgentError("Question cannot be empty.")

    # str.replace rather than .format — the prompt contains JSON braces.
    system_content = PLANNER_PROMPT.replace(
        "{{PARCEL_FIELDS}}", _fields_text(parcel_fields)
    )

    message = [
        {"role": "system", "content": system_content},
        {
            "role": "user",
            "content": (
                f"Question: {question.strip()}\n"
                f"Parcel selected: {'yes' if has_apn else 'no'}"
            ),
        },
    ]

    try:
        # A plan is a few lines of JSON — no reason to pay for 1200 tokens.
        raw = chat(message, max_tokens=300)
        data = extract_json(raw)
    except (LLMError, ValueError, json.JSONDecodeError) as err:
        return _fallback(question, has_apn, str(err)[:80])

    return {
        "needs_documents": bool(data.get("needs_documents", True)),
        # Guardrail: never plan a parcel lookup when no parcel is selected, even
        # if the model said yes.
        "needs_parcel": bool(data.get("needs_parcel")) and has_apn,
        "search_query": (data.get("search_query") or question).strip(),
        "reasoning": data.get("reasoning", ""),
        "fallback": False,
    }
