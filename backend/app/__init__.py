"""Package init — runs before any submodule is imported.

Azure App Service's Linux image ships sqlite3 older than 3.35, and chromadb raises
a RuntimeError at import time if the version is below that. `pysqlite3-binary`
bundles a modern SQLite, so swapping it into sys.modules under the name "sqlite3"
satisfies the check.

This has to happen before app.vectorstore.chroma_client is imported, which is why
it lives here: importing `app.main` loads this file first.

Windows and macOS already have a new enough sqlite3 and there is no Windows wheel
for pysqlite3-binary, so the import is optional by design.
"""
import sys

try:
    __import__("pysqlite3")
    sys.modules["sqlite3"] = sys.modules.pop("pysqlite3")
except ModuleNotFoundError:
    pass
