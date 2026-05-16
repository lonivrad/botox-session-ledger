"""Pydantic request/response schemas for the Botox Session Ledger API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Practitioner
# ---------------------------------------------------------------------------


class PractitionerCreate(BaseModel):
    name: str
    email: str


class PractitionerOut(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class ClientCreate(BaseModel):
    name: str = Field(..., examples=["Jane Smith"])
    email: Optional[str] = Field(None, examples=["jane@example.com"])
    phone: Optional[str] = Field(None, examples=["555-1234"])
    notes: Optional[str] = None
    practitioner_id: Optional[int] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None


class ClientOut(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    practitioner_id: Optional[int]
    created_at: datetime
    session_count: int = 0
    last_session_date: Optional[datetime] = None
    next_appointment_estimate: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ClientSummary(BaseModel):
    id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    session_count: int = 0
    last_session_date: Optional[datetime] = None
    next_appointment_estimate: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Vial
# ---------------------------------------------------------------------------


class VialCreate(BaseModel):
    product: str = Field("Botox", examples=["Botox"])
    lot_number: Optional[str] = Field(None, examples=["ABC123"])
    units_total: float = Field(100.0, examples=[100.0])
    diluent_ml: float = Field(..., examples=[2.5])
    cost: float = Field(656.00, examples=[656.00])
    expiry_hours: int = Field(
        24, examples=[24], description="Hours until vial expires after reconstitution"
    )
    practitioner_id: Optional[int] = None


class VialOut(BaseModel):
    id: int
    product: str
    lot_number: Optional[str]
    units_total: float
    units_remaining: float
    units_used: float
    diluent_ml: float
    concentration: float
    cost: float
    expiry_hours: int
    opened_at: Optional[datetime]
    expires_at: Optional[datetime]
    status: str
    percent_used: float
    created_at: datetime

    model_config = {"from_attributes": True}


class VialStatusUpdate(BaseModel):
    status: str = Field(..., examples=["expired"])


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


class SessionCreate(BaseModel):
    client_id: int
    vial_id: int
    session_date: Optional[datetime] = None  # defaults to now
    treatment_plan: str = Field(
        ...,
        examples=["Forehead Lines: 8 units\nFrown Lines: 12 units\nMasseters: 20 units each side"],
        description="Treatment areas and units, one per line.",
    )
    pricing_mode: str = Field("standard", examples=["standard"])
    client_charge: Optional[str] = Field(None, examples=["$420"])
    custom_price: Optional[str] = Field(None, examples=["$12/unit"])
    notes: Optional[str] = None
    practitioner_id: Optional[int] = None


class SessionAreaOut(BaseModel):
    id: int
    area_name: str
    units: float
    volume_ml: float
    u100_markings: float

    model_config = {"from_attributes": True}


class VialAllocationOut(BaseModel):
    vial_id: int
    units_allocated: float

    model_config = {"from_attributes": True}


class SessionOut(BaseModel):
    id: int
    client_id: int
    client_name: str
    session_date: datetime
    pricing_mode: str
    client_charge: Optional[float]
    recommended_charge: Optional[float]
    effective_charge: Optional[float]
    custom_price_per_unit: Optional[float]
    notes: Optional[str]
    total_units: float
    total_volume_ml: float
    total_session_cost: float
    gross_margin: Optional[float]
    gross_margin_percent: Optional[float]
    areas: list[SessionAreaOut]
    vial_allocations: list[VialAllocationOut]
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionSummary(BaseModel):
    id: int
    client_id: int
    client_name: str
    session_date: datetime
    total_units: float
    effective_charge: Optional[float]
    gross_margin_percent: Optional[float]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class RevenuePeriod(BaseModel):
    period: str
    sessions: int
    total_revenue: float
    total_cost: float
    gross_margin: float
    gross_margin_percent: float


class RevenueReport(BaseModel):
    period_type: str
    periods: list[RevenuePeriod]
    totals: RevenuePeriod


class ClientProfitability(BaseModel):
    client_id: int
    client_name: str
    sessions: int
    total_units: float
    total_revenue: float
    total_cost: float
    gross_margin: float
    gross_margin_percent: float
    last_session_date: Optional[datetime]


class WasteReport(BaseModel):
    total_vials_opened: int
    total_vials_depleted: int
    total_vials_expired: int
    estimated_waste_units: float
    estimated_waste_cost: float


class ReorderAlert(BaseModel):
    alert: bool
    message: str
    vials_in_stock: int
    active_vials: int
    avg_sessions_per_week: float
    estimated_weeks_remaining: Optional[float]
    recommended_reorder_qty: int
