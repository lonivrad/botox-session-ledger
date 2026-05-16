"""Session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.schemas import SessionAreaOut, SessionCreate, SessionOut, SessionSummary, VialAllocationOut
from app.services.session_service import create_session, get_session, list_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_out(session) -> SessionOut:  # type: ignore[no-untyped-def]
    return SessionOut(
        id=session.id,
        client_id=session.client_id,
        client_name=session.client.name,
        session_date=session.session_date,
        pricing_mode=session.pricing_mode,
        client_charge=session.client_charge,
        recommended_charge=session.recommended_charge,
        effective_charge=session.effective_charge,
        custom_price_per_unit=session.custom_price_per_unit,
        notes=session.notes,
        total_units=session.total_units,
        total_volume_ml=session.total_volume_ml,
        total_session_cost=session.total_session_cost,
        gross_margin=session.gross_margin,
        gross_margin_percent=session.gross_margin_percent,
        areas=[
            SessionAreaOut(
                id=a.id,
                area_name=a.area_name,
                units=a.units,
                volume_ml=a.volume_ml,
                u100_markings=a.u100_markings,
            )
            for a in session.areas
        ],
        vial_allocations=[
            VialAllocationOut(vial_id=va.vial_id, units_allocated=va.units_allocated)
            for va in session.vial_allocations
        ],
        created_at=session.created_at,
    )


@router.post("/", response_model=SessionOut, status_code=201)
def record_session(data: SessionCreate, db: DBSession = Depends(get_db)) -> SessionOut:
    """
    Record a treatment session. Runs the full ledger calculation,
    allocates units from the selected vial, and persists everything.
    """
    try:
        session = create_session(db, data)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_out(session)


@router.get("/", response_model=list[SessionSummary])
def get_sessions(
    client_id: int | None = None,
    limit: int = 50,
    db: DBSession = Depends(get_db),
) -> list[SessionSummary]:
    sessions = list_sessions(db, client_id=client_id, limit=limit)
    return [
        SessionSummary(
            id=s.id,
            client_id=s.client_id,
            client_name=s.client.name,
            session_date=s.session_date,
            total_units=s.total_units,
            effective_charge=s.effective_charge,
            gross_margin_percent=s.gross_margin_percent,
        )
        for s in sessions
    ]


@router.get("/{session_id}", response_model=SessionOut)
def get_single_session(session_id: int, db: DBSession = Depends(get_db)) -> SessionOut:
    session = get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_out(session)
