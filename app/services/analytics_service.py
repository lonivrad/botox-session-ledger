"""Analytics queries for revenue, profitability, waste, and reorder alerts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DBSession

from app.models import Client, Session, Vial, VialStatus
from app.schemas import (
    ClientProfitability,
    ReorderAlert,
    RevenuePeriod,
    RevenueReport,
    WasteReport,
)

# Botox typically lasts 3–4 months; use 14 weeks as the touch-up estimate
TOUCH_UP_WEEKS = 14
REORDER_LEAD_WEEKS = 2  # flag alert when stock covers < 2 weeks of sessions


def revenue_report(db: DBSession, period: str = "month") -> RevenueReport:
    """Aggregate revenue by month or quarter."""
    sessions = db.query(Session).filter(Session.gross_margin.isnot(None)).all()

    buckets: dict[str, list[Session]] = {}
    for s in sessions:
        date = s.session_date
        if period == "quarter":
            q = (date.month - 1) // 3 + 1
            key = f"{date.year} Q{q}"
        else:
            key = date.strftime("%Y-%m")
        buckets.setdefault(key, []).append(s)

    periods = []
    for key in sorted(buckets.keys()):
        bucket = buckets[key]
        revenue = sum((s.client_charge or s.recommended_charge or 0.0) for s in bucket)
        cost = sum(s.total_session_cost for s in bucket)
        margin = revenue - cost
        periods.append(
            RevenuePeriod(
                period=key,
                sessions=len(bucket),
                total_revenue=round(revenue, 2),
                total_cost=round(cost, 2),
                gross_margin=round(margin, 2),
                gross_margin_percent=round((margin / revenue * 100) if revenue else 0, 1),
            )
        )

    all_revenue = sum(p.total_revenue for p in periods)
    all_cost = sum(p.total_cost for p in periods)
    all_margin = all_revenue - all_cost

    totals = RevenuePeriod(
        period="Total",
        sessions=sum(p.sessions for p in periods),
        total_revenue=round(all_revenue, 2),
        total_cost=round(all_cost, 2),
        gross_margin=round(all_margin, 2),
        gross_margin_percent=round((all_margin / all_revenue * 100) if all_revenue else 0, 1),
    )

    return RevenueReport(period_type=period, periods=periods, totals=totals)


def client_profitability(db: DBSession) -> list[ClientProfitability]:
    """Return profitability metrics ranked by gross margin per client."""
    clients = db.query(Client).all()
    results = []

    for client in clients:
        sessions = client.sessions
        if not sessions:
            continue

        revenue = sum((s.client_charge or s.recommended_charge or 0.0) for s in sessions)
        cost = sum(s.total_session_cost for s in sessions)
        margin = revenue - cost
        total_units = sum(s.total_units for s in sessions)
        last_date = max((s.session_date for s in sessions), default=None)

        results.append(
            ClientProfitability(
                client_id=client.id,
                client_name=client.name,
                sessions=len(sessions),
                total_units=round(total_units, 1),
                total_revenue=round(revenue, 2),
                total_cost=round(cost, 2),
                gross_margin=round(margin, 2),
                gross_margin_percent=round((margin / revenue * 100) if revenue else 0, 1),
                last_session_date=last_date,
            )
        )

    return sorted(results, key=lambda x: x.gross_margin, reverse=True)


def waste_report(db: DBSession) -> WasteReport:
    """Summarise vial waste — units that expired before being used."""
    all_vials = db.query(Vial).all()
    opened = [v for v in all_vials if v.opened_at is not None]
    depleted = [v for v in opened if v.status == VialStatus.DEPLETED]
    expired = [v for v in opened if v.status == VialStatus.EXPIRED]

    waste_units = sum(v.units_remaining for v in expired)
    # Cost of wasted units proportional to vial cost
    waste_cost = sum(
        v.cost * (v.units_remaining / v.units_total) for v in expired if v.units_total > 0
    )

    return WasteReport(
        total_vials_opened=len(opened),
        total_vials_depleted=len(depleted),
        total_vials_expired=len(expired),
        estimated_waste_units=round(waste_units, 1),
        estimated_waste_cost=round(waste_cost, 2),
    )


def reorder_alert(db: DBSession) -> ReorderAlert:
    """
    Estimate whether it's time to reorder Botox.
    Uses session cadence over the last 8 weeks to project when current stock runs out.
    """
    now = datetime.now(timezone.utc)
    eight_weeks_ago = now - timedelta(weeks=8)

    recent_sessions = db.query(Session).filter(Session.session_date >= eight_weeks_ago).all()
    avg_sessions_per_week = len(recent_sessions) / 8.0

    active_vials = db.query(Vial).filter(Vial.status == VialStatus.ACTIVE).all()
    unopened_vials = db.query(Vial).filter(Vial.status == VialStatus.UNOPENED).all()
    total_stock_vials = len(active_vials) + len(unopened_vials)

    # Rough estimate: each session uses ~50-60 units on average
    if avg_sessions_per_week > 0 and total_stock_vials > 0:
        # Estimate usable units across all stock
        stock_units = sum(v.units_remaining for v in active_vials) + sum(
            v.units_total for v in unopened_vials
        )
        avg_units_per_session = (
            sum(s.total_units for s in recent_sessions) / len(recent_sessions)
            if recent_sessions
            else 55.0
        )
        weeks_remaining = stock_units / (avg_sessions_per_week * avg_units_per_session)
        alert = weeks_remaining < REORDER_LEAD_WEEKS
        message = (
            f"At current pace ({avg_sessions_per_week:.1f} sessions/week), "
            f"stock covers ~{weeks_remaining:.1f} weeks."
        )
    else:
        weeks_remaining = None
        alert = False
        message = "Not enough session history to estimate reorder timing."

    return ReorderAlert(
        alert=alert,
        message=message,
        vials_in_stock=total_stock_vials,
        active_vials=len(active_vials),
        avg_sessions_per_week=round(avg_sessions_per_week, 1),
        estimated_weeks_remaining=round(weeks_remaining, 1) if weeks_remaining else None,
        recommended_reorder_qty=max(2, round(avg_sessions_per_week * REORDER_LEAD_WEEKS)),
    )


def next_appointment_estimate(last_session_date: datetime) -> datetime:
    """Estimate when a client is due for their next touch-up."""
    return last_session_date + timedelta(weeks=TOUCH_UP_WEEKS)


def clients_due_for_touchup(db: DBSession) -> list[dict]:
    """Return clients whose estimated next appointment is within the next 4 weeks."""
    now = datetime.now(timezone.utc)
    four_weeks = now + timedelta(weeks=4)
    clients = db.query(Client).all()
    due = []

    for client in clients:
        if not client.sessions:
            continue
        last = max(client.sessions, key=lambda s: s.session_date)
        next_appt = next_appointment_estimate(last.session_date)
        if next_appt <= four_weeks:
            due.append(
                {
                    "client_id": client.id,
                    "client_name": client.name,
                    "last_session_date": last.session_date,
                    "next_appointment_estimate": next_appt,
                    "overdue": next_appt < now,
                }
            )

    return sorted(due, key=lambda x: x["next_appointment_estimate"])
