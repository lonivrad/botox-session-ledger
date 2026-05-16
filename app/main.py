"""Main FastAPI application for the Botox Session Ledger."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.routers import analytics, clients, sessions, vials

# Create tables on startup (Alembic handles migrations in production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Botox Session Ledger",
    description=(
        "Practice management for aesthetic injectable treatments. "
        "Tracks clients, vials, sessions, and profitability."
    ),
    version="2.0.0",
)

# API routers
app.include_router(clients.router)
app.include_router(vials.router)
app.include_router(sessions.router)
app.include_router(analytics.router)

# Serve frontend static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_frontend() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "2.0.0"}
