"""Generator agent — writes the final answer from the gathered sources.

Receives documents and parcel attributes; does not search for anything itself.
"""
from app.llm.openrouter_client import chat
from app.rag import SYSTEM_PROMPT, build_context

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


STRICT_SUFFIX = """

IMPORTANT — a previous answer was rejected for containing claims not supported by
the excerpts. Rewrite it so that every sentence is directly traceable to the
provided text or the parcel attributes. Drop any statement you cannot point to.
Prefer saying "the excerpts do not address this" over filling a gap."""


def _format_parcel(parcel: dict | None) -> str:
    """Labeled block describing the selected parcel.

    States absence explicitly — if the model can't see that no parcel is selected,
    it assumes a unit count instead of asking for one.
    """
    if not parcel:
        return "Selected parcel: none (no parcel selected by the user)."

    attributes = " | ".join(f"{key}: {value}" for key, value in parcel.items())
    return f"Selected parcel (real GIS attributes):\n{attributes}"


def generate_answer(
    question: str,
    documents: list[tuple],
    parcel: dict | None = None,
    strict: bool = False,
) -> dict:
    """Write the grounded answer from the retrieved sections and parcel facts."""
    if not documents and parcel is None:
        return {
            "answer": (
                "I don't have anything to work from — no relevant ordinance sections "
                "were found and no parcel is selected."
            ),
            "sources": [],
            "strict": strict,
        }

    context = build_context(documents)
    parcel_block = _format_parcel(parcel)

    system_content = GENERATOR_PROMPT + STRICT_SUFFIX if strict else GENERATOR_PROMPT

    # Question last — models weight the end of the message most heavily.
    user_content = (
        f"Municipal code excerpts:\n\n{context}\n\n"
        f"{parcel_block}\n\n"
        f"---\n\n"
        f"Question: {question}"
    )

    message = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]

    # Deliberately not caught: if generation fails there is no answer to give, so
    # let LLMError reach the router and become a 502.
    answer = chat(message, max_tokens=800)

    return {
        "answer": answer,
        "sources": [
            {
                "section": doc.metadata.get("section"),
                "title": doc.metadata.get("title"),
                "source_file": doc.metadata.get("source_file"),
                "score": round(score, 3),
            }
            for doc, score in documents
        ],
        "strict": strict,
    }
