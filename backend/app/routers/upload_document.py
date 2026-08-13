"""POST /upload_document — ingest a document into the vector store."""
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import UPLOADED_DOCUMENTS_DIR
from app.ingestion.chunker import chunk_documents
from app.ingestion.document_loader import UnsupportedFileType, load_documents
from app.vectorstore.chroma_client import add_documents

router = APIRouter()

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".xlsx", ".xls"}


@router.post("/upload_document")
def upload_document(file: UploadFile = File(...)):
    # Deliberately sync: parsing and embedding are CPU-bound with nothing to await,
    # so FastAPI runs this in a threadpool and the event loop stays free.
    # Path(...).name strips any directory component — `filename` is client-supplied,
    # so "..\..\app\config.py" would otherwise write outside the upload folder.
    safe_name = Path(file.filename or "").name
    if not safe_name:
        raise HTTPException(status_code=400, detail="No filename provided.")

    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{suffix or 'This file type'} is not supported. "
                f"Allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}"
            ),
        )

    UPLOADED_DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOADED_DOCUMENTS_DIR / safe_name

    contents = file.file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    file_path.write_bytes(contents)

    try:
        docs = load_documents(file_path)
        chunks = chunk_documents(docs)
        add_documents(chunks)
    except (UnsupportedFileType, ValueError) as err:
        # Readable problems with the file itself — don't keep the bad upload.
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:  # noqa: BLE001 - surface anything else as a 500
        raise HTTPException(
            status_code=500, detail=f"Ingestion failed: {err}"
        ) from err

    sections = sorted({c.metadata.get("section") for c in chunks if c.metadata.get("section")})

    return {
        "filename": safe_name,
        "pages": len(docs),
        "chunks": len(chunks),
        "sections": sections,
        "message": f"Indexed {len(chunks)} chunks from {safe_name}.",
    }
