"""Embedding model wrapper — text in, vector out."""
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from app.config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Load the model once and reuse it.

    Loading takes several seconds and holds ~90MB in memory, so without the cache
    every call would reload it from disk.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        # Normalizing makes cosine similarity behave predictably.
        encode_kwargs={"normalize_embeddings": True},
    )
