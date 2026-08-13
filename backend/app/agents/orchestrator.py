"""Orchestrator — runs the agents in order and assembles the response.

Holds no logic of its own beyond sequencing. It owns the request data and hands
each agent only what that agent needs.
"""
from app.agents.generator_agent import generate_answer
from app.agents.planner_agent import plan
from app.agents.retriever_reasoner_agent import retrieve_and_reason
from app.agents.validator_agent import validate


def answer(
    question: str,
    apn: str | None = None,
    parcel_attributes: dict | None = None,
) -> dict:
    """Plan, retrieve, reason, generate, validate."""
    # 1. Planner — gets the parcel's field NAMES but not their values. It decides
    #    whether parcel data is needed; it has no reason to read the values, and
    #    the names keep the prompt honest for whichever city was uploaded.
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
    #    Flags unsupported claims; no regeneration in this version.
    validation = validate(
        question, result["answer"], found["documents"], found["parcel"]
    )

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
