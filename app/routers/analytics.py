"""Analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.database import get_db
from app.schemas import ClientProfitability, ReorderAlert, RevenueReport, WasteReport
from app.services.analytics_service import (
    client_profitability,
    clients_due_for_touchup,
    reorder_alert,
    revenue_report,
    waste_report,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/revenue", response_model=RevenueReport)
def get_revenue(period: str = "month", db: DBSession = Depends(get_db)) -> RevenueReport:
    """Revenue breakdown by month or quarter."""
    return revenue_report(db, period=period)


@router.get("/clients/profitability", response_model=list[ClientProfitability])
def get_client_profitability(
    db: DBSession = Depends(get_db),
) -> list[ClientProfitability]:
    """Profitability ranked by client, highest margin first."""
    return client_profitability(db)


@router.get("/vials/waste", response_model=WasteReport)
def get_waste_report(db: DBSession = Depends(get_db)) -> WasteReport:
    """Summary of expired vials and estimated waste cost."""
    return waste_report(db)


@router.get("/reorder-alert", response_model=ReorderAlert)
def get_reorder_alert(db: DBSession = Depends(get_db)) -> ReorderAlert:
    """Reorder recommendation based on session cadence and current stock."""
    return reorder_alert(db)


@router.get("/clients/touchup-due")
def get_touchup_due(db: DBSession = Depends(get_db)) -> list[dict]:  # type: ignore[type-arg]
    """Clients whose estimated next appointment is within the next 4 weeks."""
    return clients_due_for_touchup(db)
