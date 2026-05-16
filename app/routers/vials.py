"""Vial inventory endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.schemas import VialCreate, VialOut, VialStatusUpdate
from app.services.vial_service import (
    create_vial,
    get_vial,
    list_active_vials,
    list_vials,
    update_vial_status,
)

router = APIRouter(prefix="/vials", tags=["vials"])


def _to_out(vial) -> VialOut:  # type: ignore[no-untyped-def]
    return VialOut(
        id=vial.id,
        product=vial.product,
        lot_number=vial.lot_number,
        units_total=vial.units_total,
        units_remaining=vial.units_remaining,
        units_used=vial.units_used,
        diluent_ml=vial.diluent_ml,
        concentration=vial.concentration,
        cost=vial.cost,
        expiry_hours=vial.expiry_hours,
        opened_at=vial.opened_at,
        expires_at=vial.expires_at,
        status=vial.status.value,
        percent_used_pct=round(vial.percent_used * 100, 1),
        created_at=vial.created_at,
    )


@router.post("/", response_model=VialOut, status_code=201)
def open_vial(data: VialCreate, db: DBSession = Depends(get_db)) -> VialOut:
    """Open (reconstitute) a new vial and start the expiry clock."""
    vial = create_vial(db, data)
    return _to_out(vial)


@router.get("/active", response_model=list[VialOut])
def get_active_vials(db: DBSession = Depends(get_db)) -> list[VialOut]:
    """Return all currently open, non-expired vials."""
    return [_to_out(v) for v in list_active_vials(db)]


@router.get("/", response_model=list[VialOut])
def get_all_vials(status: str | None = None, db: DBSession = Depends(get_db)) -> list[VialOut]:
    return [_to_out(v) for v in list_vials(db, status=status)]


@router.get("/{vial_id}", response_model=VialOut)
def get_single_vial(vial_id: int, db: DBSession = Depends(get_db)) -> VialOut:
    vial = get_vial(db, vial_id)
    if not vial:
        raise HTTPException(status_code=404, detail="Vial not found")
    return _to_out(vial)


@router.patch("/{vial_id}/status", response_model=VialOut)
def set_vial_status(
    vial_id: int, data: VialStatusUpdate, db: DBSession = Depends(get_db)
) -> VialOut:
    vial = get_vial(db, vial_id)
    if not vial:
        raise HTTPException(status_code=404, detail="Vial not found")
    try:
        updated = update_vial_status(db, vial, data.status)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_out(updated)
