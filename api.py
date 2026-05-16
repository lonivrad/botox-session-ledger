"""Deprecated entry-point — superseded by ``app.main``.

This shim re-exports the single FastAPI application so that any legacy
invocations (``uvicorn api:app``) continue to work without code changes.
"""

from app.main import app  # noqa: F401 — re-export
