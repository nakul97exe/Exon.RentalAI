from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import query, upload_document

# 1. Create the FastAPI app
app = FastAPI(title="Palo Alto Rental GIS", version="0.1.0")

# 2. Add CORS middleware to allow requests from the Vite dev server.
#    Explicit origins rather than "*", because a wildcard is invalid alongside
#    allow_credentials=True and browsers reject the response.
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Include the routers
app.include_router(upload_document.router, prefix="/api", tags=["Document Upload"])
app.include_router(query.router, prefix="/api", tags=["Query"])


@app.get("/health")
def health():
    """Quick check that the server is up without touching the vector store."""
    return {"status": "ok"}
