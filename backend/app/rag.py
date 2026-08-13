"""Plain RAG: retrieve once, build a grounded prompt, answer with citations.

No agents here — one retrieval, one LLM call. The agent layer later wraps this
with planning, sufficiency checks, and validation.
"""
from app.llm.openrouter_client import chat
from app.vectorstore.chroma_client import search_sections


class RAGError(Exception):
    """Raised when the question or retrieved context is unusable."""


# Correct sections score 0.5-0.7 in testing; irrelevant ones land under 0.1.
# Anything below this is noise that only burns tokens.
MIN_SCORE = 0.15

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


def answer_question(question: str, k: int = 4) -> dict:
    """Retrieve relevant sections and answer the question from them."""
    if not question or not question.strip():
        raise RAGError("Question cannot be empty.")

    results = search_sections(question, k)
    filtered = [(doc, score) for doc, score in results if score > MIN_SCORE]

    # Nothing relevant — don't spend an LLM call inventing an answer.
    if not filtered:
        return {
            "answer": (
                "I couldn't find anything relevant in the uploaded documents. "
                "Try rephrasing, or check that the right document is indexed."
            ),
            "sources": [],
            "retrieved": len(results),
        }

    context = build_context(filtered)

    message = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}\n\n---\n\nQuestion: {question}"},
    ]

    answer = chat(message)

    return {
        "answer": answer,
        "sources": [
            {
                "section": doc.metadata.get("section"),
                "title": doc.metadata.get("title"),
                "source_file": doc.metadata.get("source_file"),
                "score": round(score, 3),
            }
            for doc, score in filtered
        ],
        "retrieved": len(results),
    }
