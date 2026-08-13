"""Load any supported document type into LangChain Documents."""
from pathlib import Path


import pandas as pd
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_core.documents import Document

class UnsupportedFileType(Exception):
    """Raised when a file type is not supported by the loader."""

def load_documents(path: str | Path) -> list[Document]:
    """Dispatch to the appropriate loader based on file extension."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        docs = PyPDFLoader(str(path)).load()  # one Document per page
    else:
        raise UnsupportedFileType(f"unsupported file type: {suffix}")

    if not any(d.page_content.strip() for d in docs):
        raise ValueError(
            f"{path.name} produced no text — it may be a scanned image needing OCR."
        )

    for d in docs:
        d.metadata["source_file"] = path.name   

    return docs;

