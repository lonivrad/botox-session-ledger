"""Session creation service — bridges the API layer with botox_session_ledger.py."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session as DBSession

from app.models import Client, Session, SessionArea, Vial, VialAllocation
from app.schemas import SessionCreate
from app.services.vial_service import allocate_units, refresh_expired_vials
from botox_session_ledger import build_ledger_data, parse_custom_price, parse_money


def create_session(db: DBSession, data: SessionCreate) -> Session:
    """
    Create a treatment session:
    1. Run the ledger calculation using the existing botox_session_ledger core.
    2. Allocate units from the specified vial.
    3. Persist session, areas, and allocation.
    """
    refresh_expired_vials(db)

    vial: Vial | None = db.get(Vial, data.vial_id)
    if vial is None:
        raise ValueError(f"Vial {data.vial_id} not found.")
    if vial.status.value not in ("active",):
        raise ValueError(
            f"Vial {data.vial_id} is not active (status: {vial.status.value}). "
            "Only active vials can be used for treatment."
        )

    client: Client | None = db.get(Client, data.client_id)
    if client is None:
        raise ValueError(f"Client {data.client_id} not found.")

    diluent_text = f"{vial.diluent_ml} mL"

    # Run core ledger calculations (semicolons normalised inside build_ledger_data)
    ledger = build_ledger_data(
        client=client.name,
        product=vial.product,
        diluent_text=diluent_text,
        treatment_plan=data.treatment_plan,
        pricing_mode=data.pricing_mode,
        client_charge=data.client_charge,
        custom_price=data.custom_price,
    )

    if ledger.total_units > vial.units_remaining:
        raise ValueError(
            f"Insufficient vial inventory: need {ledger.total_units} units, "
            f"only {vial.units_remaining:.1f} remaining in vial {data.vial_id}."
        )

    session_date = data.session_date or datetime.now(timezone.utc)

    # Parse money values for storage using the canonical parsers from the core lib.
    # These raise InvalidMoneyError / InvalidPricingError on bad input, which is the
    # correct behaviour (the ledger calculation above already validated the strings, so
    # reaching here with an invalid value would be a programmer error, not a user error).
    client_charge_float: float | None = parse_money(data.client_charge)
    custom_price_float: float | None = parse_custom_price(data.custom_price)

    session = Session(
        client_id=data.client_id,
        practitioner_id=data.practitioner_id,
        session_date=session_date,
        pricing_mode=data.pricing_mode,
        client_charge=client_charge_float,
        custom_price_per_unit=custom_price_float,
        notes=data.notes,
        total_units=ledger.total_units,
        total_volume_ml=ledger.total_volume_ml,
        total_session_cost=ledger.costs.total_session_cost_mid,
        gross_margin=ledger.pricing.gross_margin,
        gross_margin_percent=ledger.pricing.gross_margin_percent,
        recommended_charge=ledger.pricing.recommended_charge,
    )
    db.add(session)
    db.flush()  # get session.id without committing

    # Persist treatment areas
    for entry in ledger.entries:
        db.add(
            SessionArea(
                session_id=session.id,
                area_name=entry.area,
                units=entry.units,
                volume_ml=entry.volume_ml,
                u100_markings=entry.u100_markings,
            )
        )

    # Allocate from vial
    db.add(
        VialAllocation(
            vial_id=vial.id,
            session_id=session.id,
            units_allocated=ledger.total_units,
        )
    )
    allocate_units(db, vial, ledger.total_units)

    db.commit()
    db.refresh(session)
    return session


def get_session(db: DBSession, session_id: int) -> Session | None:
    return db.get(Session, session_id)


def list_sessions(db: DBSession, client_id: int | None = None, limit: int = 50) -> list[Session]:
    query = db.query(Session)
    if client_id is not None:
        query = query.filter(Session.client_id == client_id)
    return query.order_by(Session.session_date.desc()).limit(limit).all()
