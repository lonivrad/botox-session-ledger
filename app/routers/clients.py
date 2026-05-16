"""Client CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.models import Client
from app.schemas import ClientCreate, ClientOut, ClientSummary, ClientUpdate
from app.services.analytics_service import next_appointment_estimate

router = APIRouter(prefix="/clients", tags=["clients"])


def _enrich(client: Client) -> ClientOut:
    sessions = client.sessions
    # Relationship is ordered by session_date DESC, so the most recent is first.
    last_session = sessions[0] if sessions else None
    next_appt = next_appointment_estimate(last_session.session_date) if last_session else None
    return ClientOut(
        id=client.id,
        name=client.name,
        email=client.email,
        phone=client.phone,
        notes=client.notes,
        practitioner_id=client.practitioner_id,
        created_at=client.created_at,
        session_count=len(sessions),
        last_session_date=last_session.session_date if last_session else None,
        next_appointment_estimate=next_appt,
    )


@router.post("/", response_model=ClientOut, status_code=201)
def create_client(data: ClientCreate, db: DBSession = Depends(get_db)) -> ClientOut:
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return _enrich(client)


@router.get("/", response_model=list[ClientSummary])
def list_clients(db: DBSession = Depends(get_db)) -> list[ClientSummary]:
    clients = db.query(Client).order_by(Client.name).all()
    result = []
    for c in clients:
        sessions = c.sessions
        last = sessions[0] if sessions else None  # relationship is ordered DESC
        result.append(
            ClientSummary(
                id=c.id,
                name=c.name,
                email=c.email,
                phone=c.phone,
                session_count=len(sessions),
                last_session_date=last.session_date if last else None,
                next_appointment_estimate=(
                    next_appointment_estimate(last.session_date) if last else None
                ),
            )
        )
    return result


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: int, db: DBSession = Depends(get_db)) -> ClientOut:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _enrich(client)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: int, data: ClientUpdate, db: DBSession = Depends(get_db)) -> ClientOut:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return _enrich(client)
