# Botox Session Ledger

![CI](https://github.com/lonivrad/botox-session-ledger/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue)

A full-stack practice management tool for aesthetic injectable treatments. Tracks clients, vial lifecycle, sessions, and profitability — all from a local SQLite database with a browser-based dashboard.

---

## Why I Built This

I work in healthcare and perform aesthetic injectable treatments. In real-world practice, small math mistakes, unit confusion, and incomplete cost visibility directly impact inventory tracking, profitability, pricing consistency, and operational efficiency.

This started as a reusable calculation script. It's now a complete practice operations tool.

---

## What It Does

- **Clients** — full client records with session history and touch-up scheduling
- **Vials** — lifecycle state machine (unopened → active → depleted / expired), real-time inventory tracking with concentration preview
- **Sessions** — treatment plan entry with automatic cost and margin calculation powered by the original ledger engine
- **Analytics** — monthly/quarterly revenue, per-client profitability, waste reporting, reorder alerts
- **Dashboard** — browser UI with KPI cards, upcoming touch-up list, revenue chart, profitability table

This is not a clinical dosing tool. It only performs operational and financial calculations using user-provided treatment values.

---

## Project Structure

```text
botox-session-ledger/
├── botox_session_ledger.py        ← core calculation engine (v1, preserved)
├── api.py                         ← deprecated shim; re-exports app from app.main
├── app/
│   ├── main.py                    ← FastAPI app, /ledger endpoint, static serving
│   ├── database.py                ← SQLAlchemy engine, SessionLocal, Base
│   ├── models.py                  ← ORM models (Client, Vial, Session, etc.)
│   ├── schemas.py                 ← Pydantic v2 request/response schemas
│   ├── routers/
│   │   ├── clients.py             ← /clients CRUD
│   │   ├── vials.py               ← /vials lifecycle
│   │   ├── sessions.py            ← /sessions
│   │   └── analytics.py          ← /analytics/*
│   ├── services/
│   │   ├── vial_service.py        ← vial lifecycle + allocation logic
│   │   ├── session_service.py     ← session creation, calls ledger engine
│   │   └── analytics_service.py  ← revenue, profitability, waste, reorder
│   └── static/
│       ├── index.html             ← single-page dashboard markup
│       ├── style.css              ← all custom styles
│       └── app.js                 ← all frontend logic (Tailwind + Chart.js)
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 001_initial_schema.py
├── tests/
│   ├── conftest.py
│   ├── test_ledger.py             ← unit tests for the calculation engine
│   └── test_api.py                ← HTTP contract tests for the API surface
├── alembic.ini
├── Dockerfile
├── Makefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── .github/
    └── workflows/
        └── ci.yml
```

---

## Quick Start

```bash
cd ~/code/botox-session-ledger

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

Then open **http://localhost:8000** in your browser.

---

## Makefile Commands

```bash
make install    # pip install -r requirements-dev.txt
make run        # uvicorn app.main:app --reload
make migrate    # alembic upgrade head
make test       # pytest with coverage
make lint       # ruff check .
make typecheck  # mypy strict
make clean      # remove __pycache__, .pytest_cache, .pyc
```

---

## Docker

```bash
docker build -t botox-ledger .
docker run -p 8000:8000 botox-ledger
```

The container runs `alembic upgrade head` then starts uvicorn. Mount a volume to persist the SQLite database:

```bash
docker run -p 8000:8000 -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite:///./data/ledger.db \
  botox-ledger
```

---

## API Reference

All endpoints return JSON. The interactive docs are at **http://localhost:8000/docs**.

### Clients

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/clients` | Create a client |
| `GET` | `/clients` | List all clients |
| `GET` | `/clients/{id}` | Get client + session history |
| `PATCH` | `/clients/{id}` | Update client |

### Vials

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/vials` | Open a new vial |
| `GET` | `/vials/active` | List active vials (auto-expires stale ones) |
| `GET` | `/vials` | List all vials |
| `GET` | `/vials/{id}` | Get vial detail |
| `PATCH` | `/vials/{id}/status` | Manually update vial status |

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/sessions` | Record a session |
| `GET` | `/sessions` | List sessions (filter by `?client_id=`) |
| `GET` | `/sessions/{id}` | Get session detail with area breakdown |

### Analytics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/analytics/revenue` | Revenue by period (`?period=month\|quarter`) |
| `GET` | `/analytics/clients/profitability` | Per-client revenue, cost, margin |
| `GET` | `/analytics/vials/waste` | Expired vial waste summary |
| `GET` | `/analytics/reorder-alert` | Stock runway estimate, reorder flag |
| `GET` | `/analytics/clients/touchup-due` | Clients due for a touch-up within 4 weeks |

---

## Data Model

```
Practitioner (nullable FK throughout — ready for multi-user, no auth required today)
    └── Client
            └── Session
                    ├── SessionArea (per-area units, volume, U-100 markings)
                    └── VialAllocation → Vial
```

**Vial states:** `unopened` → `active` → `depleted` | `expired`

**Pricing modes:** `standard` (20% target margin) | `family_friend` ($10/unit) | `custom` ($/unit)

---

## Calculation Engine

`botox_session_ledger.py` is the original v1 script, preserved intact as the calculation core. When a session is created, `session_service.py` calls `build_ledger_data()` from this module — so all unit tests continue to pass and the math is identical to the original.

The engine handles:

- Dilution calculation (`100 units ÷ diluent mL`)
- Per-area volume (`units ÷ concentration`)
- U-100 syringe markings
- Consumables cost (product, saline, syringes, gloves, prep pads)
- Gross margin and recommended pricing across all three pricing modes

---

## Custom Exceptions

```python
from botox_session_ledger import (
    BotoxLedgerError,         # base
    InvalidDiluentError,
    InvalidTreatmentPlanError,
    InvalidPricingError,
    InvalidMoneyError,
)
```

All validation errors subclass `BotoxLedgerError` (itself a `ValueError`), so existing `except ValueError` handlers still work.

---

## CI

GitHub Actions runs on every push:

1. `ruff check .` — linting
2. `mypy --strict` — type checking
3. `pytest --cov-fail-under=80` — tests with coverage gate

---

## Production Considerations

**Authentication is intentionally out of scope for this demo.** The API has no auth layer — any request can read or write any record. A production deployment would add OAuth2/JWT via FastAPI's built-in security utilities (`OAuth2PasswordBearer`, dependency-injected `get_current_user`), with per-practitioner row-level scoping on all queries. The data model already carries a `practitioner_id` foreign key throughout in anticipation of this.

Other production concerns not addressed here: HTTPS termination, secrets management, a persistent Postgres database (swap the `DATABASE_URL` env var), rate limiting, and audit logging.

---

## Limitations

This tool does not account for malpractice insurance, provider compensation, payroll, rent, taxes, merchant processing fees, licensing, marketing, spoilage, financing, or any fixed operating expenses.

It does not make clinical decisions. All treatment unit values must be provided by the practitioner.
