"""SQLAlchemy ORM models for the Botox Session Ledger application."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class VialStatus(str, enum.Enum):
    UNOPENED = "unopened"
    ACTIVE = "active"
    DEPLETED = "depleted"
    EXPIRED = "expired"


class PricingMode(str, enum.Enum):
    STANDARD = "standard"
    FAMILY_FRIEND = "family-friend"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class Practitioner(Base):
    """A practitioner who performs treatments. Hook for future multi-user support."""

    __tablename__ = "practitioners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    clients: Mapped[list[Client]] = relationship("Client", back_populates="practitioner")
    vials: Mapped[list[Vial]] = relationship("Vial", back_populates="practitioner")
    sessions: Mapped[list[Session]] = relationship("Session", back_populates="practitioner")


class Client(Base):
    """A client who receives treatments."""

    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practitioner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("practitioners.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    practitioner: Mapped[Practitioner | None] = relationship(
        "Practitioner", back_populates="clients"
    )
    sessions: Mapped[list[Session]] = relationship(
        "Session", back_populates="client", order_by="Session.session_date.desc()"
    )


class Vial(Base):
    """A single Botox vial with lifecycle tracking."""

    __tablename__ = "vials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practitioner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("practitioners.id"), nullable=True
    )
    product: Mapped[str] = mapped_column(String(100), nullable=False, default="Botox")
    lot_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    units_total: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    units_remaining: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    diluent_ml: Mapped[float] = mapped_column(Float, nullable=False)
    concentration: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=656.00)
    expiry_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[VialStatus] = mapped_column(
        Enum(VialStatus), nullable=False, default=VialStatus.UNOPENED
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    practitioner: Mapped[Practitioner | None] = relationship("Practitioner", back_populates="vials")
    allocations: Mapped[list[VialAllocation]] = relationship(
        "VialAllocation", back_populates="vial"
    )

    @property
    def units_used(self) -> float:
        return self.units_total - self.units_remaining

    @property
    def percent_used(self) -> float:
        """Fraction of vial used, 0.0–1.0. Multiply by 100 for a display percentage."""
        return self.units_used / self.units_total if self.units_total > 0 else 0.0

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class Session(Base):
    """A single treatment session for a client."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, ForeignKey("clients.id"), nullable=False)
    practitioner_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("practitioners.id"), nullable=True
    )
    session_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pricing_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="standard")
    client_charge: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_price_per_unit: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Computed and stored at session creation time
    total_units: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_volume_ml: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_session_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    gross_margin_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_charge: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped[Client] = relationship("Client", back_populates="sessions")
    practitioner: Mapped[Practitioner | None] = relationship(
        "Practitioner", back_populates="sessions"
    )
    areas: Mapped[list[SessionArea]] = relationship(
        "SessionArea", back_populates="session", cascade="all, delete-orphan"
    )
    vial_allocations: Mapped[list[VialAllocation]] = relationship(
        "VialAllocation", back_populates="session", cascade="all, delete-orphan"
    )

    @property
    def effective_charge(self) -> float | None:
        # Use `is not None` rather than truthiness so that a comped session
        # (client_charge == 0.0) is preserved correctly instead of falling
        # through to recommended_charge.
        return self.client_charge if self.client_charge is not None else self.recommended_charge


class SessionArea(Base):
    """One treatment area within a session."""

    __tablename__ = "session_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    area_name: Mapped[str] = mapped_column(String(255), nullable=False)
    units: Mapped[float] = mapped_column(Float, nullable=False)
    volume_ml: Mapped[float] = mapped_column(Float, nullable=False)
    u100_markings: Mapped[float] = mapped_column(Float, nullable=False)

    session: Mapped[Session] = relationship("Session", back_populates="areas")


class VialAllocation(Base):
    """Records how many units a session drew from a specific vial."""

    __tablename__ = "vial_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vial_id: Mapped[int] = mapped_column(Integer, ForeignKey("vials.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id"), nullable=False)
    units_allocated: Mapped[float] = mapped_column(Float, nullable=False)

    vial: Mapped[Vial] = relationship("Vial", back_populates="allocations")
    session: Mapped[Session] = relationship("Session", back_populates="vial_allocations")
