"""Central config — paths and model names in one place."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
CHROMA_DIR = DATA_DIR / "chroma_store"
UPLOADED_DOCUMENTS_DIR = DATA_DIR / "uploaded_documents"
UPLOADED_SHAPEFILES_DIR = DATA_DIR / "uploaded_shapefiles"

# 384 dims, ~90MB, 256-token window — the chunker's 1000-char limit matches this.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ordinances")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
