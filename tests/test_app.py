"""
Integration tests for the app/ CRUD layer.

Each test gets a clean database (conftest._clean_tables wipes rows after every test).
These tests exercise routers, services, and the database layer end-to-end.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mk_client(c: TestClient, name: str = "Test Client") -> dict:  # type: ignore[type-arg]
    resp = c.post("/clients/", json={"name": name})
    assert resp.status_code == 201
    return resp.json()  # type: ignore[no-any-return]


def _mk_vial(c: TestClient, units: float = 100.0, diluent: float = 2.5) -> dict:  # type: ignore[type-arg]
    resp = c.post("/vials/", json={"diluent_ml": diluent, "units_total": units})
    assert resp.status_code == 201
    return resp.json()  # type: ignore[no-any-return]


_PLAN = "Forehead Lines: 10 units\nFrown Lines: 15 units"


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

class TestClients:
    def test_create_returns_201(self, api_client: TestClient) -> None:
        assert api_client.post("/clients/", json={"name": "Alice"}).status_code == 201

    def test_create_stores_fields(self, api_client: TestClient) -> None:
        data = api_client.post(
            "/clients/", json={"name": "Alice", "email": "alice@example.com", "phone": "555-1234"}
        ).json()
        assert data["name"] == "Alice"
        assert data["email"] == "alice@example.com"
        assert data["session_count"] == 0

    def test_list_clients(self, api_client: TestClient) -> None:
        _mk_client(api_client, "Bob")
        _mk_client(api_client, "Carol")
        resp = api_client.get("/clients/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_client(self, api_client: TestClient) -> None:
        created = _mk_client(api_client, "Dave")
        resp = api_client.get(f"/clients/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Dave"

    def test_get_client_not_found(self, api_client: TestClient) -> None:
        assert api_client.get("/clients/99999").status_code == 404

    def test_update_client(self, api_client: TestClient) -> None:
        created = _mk_client(api_client, "Eve")
        resp = api_client.patch(f"/clients/{created['id']}", json={"email": "eve@example.com"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "eve@example.com"

    def test_update_client_not_found(self, api_client: TestClient) -> None:
        assert api_client.patch("/clients/99999", json={"email": "x@x.com"}).status_code == 404


# ---------------------------------------------------------------------------
# Vials
# ---------------------------------------------------------------------------

class TestVials:
    def test_open_vial_returns_201_active(self, api_client: TestClient) -> None:
        resp = api_client.post("/vials/", json={"diluent_ml": 2.5})
        assert resp.status_code == 201
        assert resp.json()["status"] == "active"

    def test_concentration_calculated(self, api_client: TestClient) -> None:
        data = api_client.post("/vials/", json={"diluent_ml": 2.5, "units_total": 100.0}).json()
        assert data["concentration"] == pytest.approx(40.0)

    def test_list_active_vials(self, api_client: TestClient) -> None:
        _mk_vial(api_client)
        resp = api_client.get("/vials/active")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_list_all_vials(self, api_client: TestClient) -> None:
        _mk_vial(api_client)
        _mk_vial(api_client)
        resp = api_client.get("/vials/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_list_vials_filter_by_status(self, api_client: TestClient) -> None:
        _mk_vial(api_client)
        resp = api_client.get("/vials/?status=active")
        assert resp.status_code == 200

    def test_get_vial(self, api_client: TestClient) -> None:
        created = _mk_vial(api_client)
        resp = api_client.get(f"/vials/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["id"] == created["id"]

    def test_get_vial_not_found(self, api_client: TestClient) -> None:
        assert api_client.get("/vials/99999").status_code == 404

    def test_update_vial_status(self, api_client: TestClient) -> None:
        created = _mk_vial(api_client)
        resp = api_client.patch(f"/vials/{created['id']}/status", json={"status": "depleted"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "depleted"

    def test_update_vial_invalid_status(self, api_client: TestClient) -> None:
        created = _mk_vial(api_client)
        resp = api_client.patch(f"/vials/{created['id']}/status", json={"status": "nonsense"})
        assert resp.status_code == 422

    def test_update_vial_not_found(self, api_client: TestClient) -> None:
        assert api_client.patch("/vials/99999/status", json={"status": "depleted"}).status_code == 404


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class TestSessions:
    def test_record_session_returns_201(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        resp = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        })
        assert resp.status_code == 201

    def test_session_total_units(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        data = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        }).json()
        assert data["total_units"] == pytest.approx(25.0)

    def test_session_deducts_vial_units(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        })
        assert api_client.get(f"/vials/{v['id']}").json()["units_remaining"] == pytest.approx(75.0)

    def test_session_stores_client_charge(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        data = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
            "client_charge": "$400",
        }).json()
        assert data["client_charge"] == pytest.approx(400.0)

    def test_session_area_breakdown(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        data = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        }).json()
        assert len(data["areas"]) == 2

    def test_session_missing_client_422(self, api_client: TestClient) -> None:
        v = _mk_vial(api_client)
        resp = api_client.post("/sessions/", json={
            "client_id": 99999, "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        })
        assert resp.status_code == 422

    def test_session_missing_vial_422(self, api_client: TestClient) -> None:
        c = _mk_client(api_client)
        resp = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": 99999,
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        })
        assert resp.status_code == 422

    def test_session_insufficient_units_422(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client, units=10.0)
        resp = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": "Forehead: 50 units", "pricing_mode": "standard",
        })
        assert resp.status_code == 422

    def test_session_inactive_vial_422(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        api_client.patch(f"/vials/{v['id']}/status", json={"status": "depleted"})
        resp = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        })
        assert resp.status_code == 422

    def test_list_sessions(self, api_client: TestClient) -> None:
        assert api_client.get("/sessions/").status_code == 200

    def test_list_sessions_filter_by_client(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": "Forehead: 5 units", "pricing_mode": "standard",
        })
        resp = api_client.get(f"/sessions/?client_id={c['id']}")
        assert len(resp.json()) == 1

    def test_get_session(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        created = api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        }).json()
        resp = api_client.get(f"/sessions/{created['id']}")
        assert resp.status_code == 200

    def test_get_session_not_found(self, api_client: TestClient) -> None:
        assert api_client.get("/sessions/99999").status_code == 404


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class TestAnalytics:
    def test_revenue_report_empty(self, api_client: TestClient) -> None:
        resp = api_client.get("/analytics/revenue")
        assert resp.status_code == 200
        assert resp.json()["period_type"] == "month"

    def test_revenue_report_quarter(self, api_client: TestClient) -> None:
        resp = api_client.get("/analytics/revenue?period=quarter")
        assert resp.status_code == 200
        assert resp.json()["period_type"] == "quarter"

    def test_client_profitability_empty(self, api_client: TestClient) -> None:
        resp = api_client.get("/analytics/clients/profitability")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_waste_report(self, api_client: TestClient) -> None:
        resp = api_client.get("/analytics/vials/waste")
        assert resp.status_code == 200
        assert "total_vials_opened" in resp.json()

    def test_reorder_alert(self, api_client: TestClient) -> None:
        resp = api_client.get("/analytics/reorder-alert")
        assert resp.status_code == 200
        assert "alert" in resp.json()

    def test_touchup_due(self, api_client: TestClient) -> None:
        resp = api_client.get("/analytics/clients/touchup-due")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_revenue_with_data(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
            "client_charge": "$400",
        })
        data = api_client.get("/analytics/revenue").json()
        assert data["totals"]["sessions"] == 1
        assert data["totals"]["total_revenue"] == pytest.approx(400.0)

    def test_client_profitability_with_data(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client, "Profitable Client"), _mk_vial(api_client)
        api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
            "client_charge": "$500",
        })
        results = api_client.get("/analytics/clients/profitability").json()
        assert len(results) == 1
        assert results[0]["client_name"] == "Profitable Client"

    def test_waste_report_with_expired_vial(self, api_client: TestClient) -> None:
        v = _mk_vial(api_client)
        api_client.patch(f"/vials/{v['id']}/status", json={"status": "expired"})
        data = api_client.get("/analytics/vials/waste").json()
        assert data["total_vials_expired"] == 1

    def test_reorder_alert_with_sessions(self, api_client: TestClient) -> None:
        c, v = _mk_client(api_client), _mk_vial(api_client)
        api_client.post("/sessions/", json={
            "client_id": c["id"], "vial_id": v["id"],
            "treatment_plan": _PLAN, "pricing_mode": "standard",
        })
        data = api_client.get("/analytics/reorder-alert").json()
        assert "avg_sessions_per_week" in data
