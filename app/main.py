"""Main FastAPI application for the Botox Session Ledger."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.database import Base, engine
from app.routers import analytics, clients, sessions, vials
from botox_session_ledger import build_ledger_data, ledger_to_dict

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

class LedgerRequest(BaseModel):
    client: str = Field(..., examples=["Jane"])
    product: str = Field("Botox", examples=["Botox"])
    diluent: str = Field(
        ...,
        examples=["2.5 mL"],
        description="Diluent volume used to reconstitute the vial, e.g. '2.5 mL'.",
    )
    treatment_plan: str = Field(
        ...,
        examples=["Forehead Lines: 8 units\nFrown Lines: 12 units\nMasseters: 20 units each side"],
        description="Treatment areas and units, one per line. Semicolons are accepted as line separators.",
    )
    pricing_mode: str = Field(
        "standard",
        examples=["standard"],
        description="Pricing strategy: 'standard' (20% margin), 'family-friend' ($10/unit), or 'custom'.",
    )
    client_charge: str | None = Field(
        None,
        examples=["$420"],
        description="Actual amount charged. If omitted, a recommended charge is calculated.",
    )
    custom_price: str | None = Field(
        None,
        examples=["$12/unit"],
        description="Required when pricing_mode is 'custom'.",
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


@app.post("/ledger", tags=["ledger"])
def create_ledger(request: LedgerRequest) -> dict[str, Any]:
    """
    Generate a structured Botox session ledger.

    Returns per-area volumes and U-100 markings, vial reconciliation,
    itemised consumable costs, and gross margin analysis.

    Raises 422 on invalid inputs (bad diluent format, mg/mcg units, negative values, etc.).
    """
    try:
        data = build_ledger_data(
            client=request.client,
            product=request.product,
            diluent_text=request.diluent,
            treatment_plan=request.treatment_plan,  # semicolons normalised inside build_ledger_data
            pricing_mode=request.pricing_mode,
            client_charge=request.client_charge,
            custom_price=request.custom_price,
        )
        return ledger_to_dict(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
