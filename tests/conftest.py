"""Shared pytest fixtures and test database setup."""

from __future__ import annotations

import os
import sys

# Add repo root to path so botox_session_ledger.py is importable directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# In-memory test database.
# StaticPool forces all connections to share the same in-memory SQLite
# database, which avoids the "each connection gets its own DB" problem and
# requires no disk writes (safe on virtiofs / CI alike).
# ---------------------------------------------------------------------------
_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db() -> object:
    db = _TestSession()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Override get_db globally so all TestClient instances use the test database
app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> object:
    """Create all tables once for the test session."""
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture(autouse=True)
def _clean_tables() -> object:
    """Wipe all rows after each test for full isolation."""
    yield
    db = _TestSession()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()


@pytest.fixture
def api_client() -> object:
    with TestClient(app) as c:
        yield c
