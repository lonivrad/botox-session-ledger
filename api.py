"""
FastAPI wrapper for the Botox Session Ledger.

Run locally:
    pip install fastapi uvicorn
    uvicorn api:app --reload

Interactive docs: http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from botox_session_ledger import build_ledger_data, ledger_to_dict

app = FastAPI(
    title="Botox Session Ledger API",
    description=(
        "Converts a Botox treatment plan into a structured session ledger with "
        "concentration math, vial reconciliation, itemized costs, and pricing analysis. "
        "Does not provide clinical dosing recommendations."
    ),
    version="1.0.0",
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


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Returns API liveness status."""
    return {"status": "ok"}


@app.post("/ledger", tags=["ledger"])
def create_ledger(request: LedgerRequest) -> dict[str, Any]:
    """
    Generate a structured Botox session ledger.

    Returns per-area volumes and U-100 markings, vial reconciliation,
    itemized consumable costs, and gross margin analysis.

    Raises 422 on invalid inputs (bad diluent format, mg/mcg units, negative values, etc.).
    """
    treatment_plan = request.treatment_plan.replace(";", "\n")

    try:
        data = build_ledger_data(
            client=request.client,
            product=request.product,
            diluent_text=request.diluent,
            treatment_plan=treatment_plan,
            pricing_mode=request.pricing_mode,
            client_charge=request.client_charge,
            custom_price=request.custom_price,
        )
        return ledger_to_dict(data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
