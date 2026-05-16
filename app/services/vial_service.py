"""Vial lifecycle business logic."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DBSession

from app.models import Vial, VialStatus
from app.schemas import VialCreate


def create_vial(db: DBSession, data: VialCreate) -> Vial:
    """Create and immediately reconstitute (open) a new vial."""
    now = datetime.now(timezone.utc)
    concentration = data.units_total / data.diluent_ml
    expires_at = now + timedelta(hours=data.expiry_hours)

    vial = Vial(
        product=data.product,
        lot_number=data.lot_number,
        units_total=data.units_total,
        units_remaining=data.units_total,
        diluent_ml=data.diluent_ml,
        concentration=concentration,
        cost=data.cost,
        expiry_hours=data.expiry_hours,
        opened_at=now,
        expires_at=expires_at,
        status=VialStatus.ACTIVE,
        practitioner_id=data.practitioner_id,
    )
    db.add(vial)
    db.commit()
    db.refresh(vial)
    return vial


def get_vial(db: DBSession, vial_id: int) -> Vial | None:
    return db.get(Vial, vial_id)


def list_vials(db: DBSession, status: str | None = None) -> list[Vial]:
    query = db.query(Vial)
    if status:
        query = query.filter(Vial.status == status)
    return query.order_by(Vial.created_at.desc()).all()


def list_active_vials(db: DBSession) -> list[Vial]:
    """Return vials that are currently open and not expired."""
    refresh_expired_vials(db)
    return db.query(Vial).filter(Vial.status == VialStatus.ACTIVE).all()


def refresh_expired_vials(db: DBSession) -> int:
    """Mark any active vials past their expiry time as expired. Returns count updated."""
    now = datetime.now(timezone.utc)
    expired = db.query(Vial).filter(Vial.status == VialStatus.ACTIVE, Vial.expires_at <= now).all()
    for vial in expired:
        vial.status = VialStatus.EXPIRED
    if expired:
        db.commit()
    return len(expired)


def allocate_units(db: DBSession, vial: Vial, units: float) -> None:
    """Deduct units from a vial and mark depleted if empty."""
    vial.units_remaining = round(vial.units_remaining - units, 4)
    if vial.units_remaining <= 0:
        vial.units_remaining = 0.0
        vial.status = VialStatus.DEPLETED
    db.flush()


def update_vial_status(db: DBSession, vial: Vial, status: str) -> Vial:
    vial.status = VialStatus(status)
    db.commit()
    db.refresh(vial)
    return vial
