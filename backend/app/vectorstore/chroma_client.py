"""Chroma vector store — add chunks, search chunks.

Chroma here is an embedded library, not a server: it writes files into
data/chroma_store/ and there is nothing to start or connect to.
"""
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import CHROMA_DIR, COLLECTION_NAME
from app.vectorstore.embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_store() -> Chroma:
    """Open (or create) the persisted collection."""
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def _chunk_id(doc: Document) -> str:
    """Stable id built from the chunk's own metadata.

    Re-uploading the same document overwrites these rows instead of storing a
    second copy of every chunk — without this, uploading twice would duplicate
    every search result.
    """
    m = doc.metadata
    return f"{m.get('source_file', 'unknown')}::{m.get('section', '0')}::{m.get('part', 1)}"


def add_documents(docs: list[Document]) -> list[str]:
    """Embed and store chunks. Returns the ids written."""
    if not docs:
        return []

    ids = [_chunk_id(d) for d in docs]
    get_store().add_documents(documents=docs, ids=ids)
    return ids


def search(query: str, k: int = 4, source_file: str | None = None):
    """Raw similarity search. Returns [(Document, score), ...], best first."""
    where = {"source_file": source_file} if source_file else None
    return get_store().similarity_search_with_relevance_scores(query, k=k, filter=where)


def get_full_section(source_file: str, section: str) -> Document | None:
    """Rebuild a complete section from its stored parts."""
    rows = get_store().get(
        where={
            "$and": [
                {"source_file": {"$eq": source_file}},
                {"section": {"$eq": section}},
            ]
        }
    )
    if not rows["ids"]:
        return None

    ordered = sorted(
        zip(rows["metadatas"], rows["documents"]),
        key=lambda pair: pair[0].get("part", 1),
    )

    meta = dict(ordered[0][0])
    meta.pop("part", None)
    meta.pop("parts", None)

    return Document(
        page_content="\n".join(text for _, text in ordered),
        metadata=meta,
    )


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


def count() -> int:
    """How many chunks are currently stored."""
    return get_store()._collection.count()
