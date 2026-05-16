"""
Integration tests for the FastAPI ledger endpoint.

Uses FastAPI's built-in TestClient (backed by httpx) — no server needed.
"""

import sys
import os

# Ensure api.py at the repo root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

JANE_PAYLOAD = {
    "client": "Jane",
    "product": "Botox",
    "diluent": "2.5 mL",
    "treatment_plan": (
        "Forehead Lines: 8 units\n"
        "Frown Lines: 12 units\n"
        "Masseters: 20 units each side"
    ),
    "pricing_mode": "standard",
    "client_charge": "$420",
}


class TestHealthEndpoint:
    def test_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_returns_ok_status(self):
        assert client.get("/health").json() == {"status": "ok"}


class TestLedgerEndpoint:
    def test_valid_request_returns_200(self):
        resp = client.post("/ledger", json=JANE_PAYLOAD)
        assert resp.status_code == 200

    def test_response_is_valid_json(self):
        resp = client.post("/ledger", json=JANE_PAYLOAD)
        assert resp.headers["content-type"] == "application/json"
        data = resp.json()
        assert isinstance(data, dict)

    def test_response_top_level_fields(self):
        data = client.post("/ledger", json=JANE_PAYLOAD).json()
        for field in ("client", "product", "entries", "costs", "pricing", "flags"):
            assert field in data, f"Missing field: {field}"

    def test_total_units_correct(self):
        # 8 + 12 + (20 * 2) = 60
        assert client.post("/ledger", json=JANE_PAYLOAD).json()["total_units"] == 60.0

    def test_total_volume_correct(self):
        # 60 units / 40 units/mL = 1.5 mL
        assert client.post("/ledger", json=JANE_PAYLOAD).json()["total_volume_ml"] == 1.5

    def test_entries_list_length(self):
        # 3 treatment lines → 3 entries (masseters count as one bilateral entry)
        entries = client.post("/ledger", json=JANE_PAYLOAD).json()["entries"]
        assert len(entries) == 3

    def test_entries_contain_expected_fields(self):
        entry = client.post("/ledger", json=JANE_PAYLOAD).json()["entries"][0]
        for field in ("area", "units", "volume_ml", "u100_markings"):
            assert field in entry

    def test_costs_contain_expected_fields(self):
        costs = client.post("/ledger", json=JANE_PAYLOAD).json()["costs"]
        for field in ("botox_product_cost_used", "syringes_required", "total_session_cost_mid"):
            assert field in costs

    def test_pricing_contains_expected_fields(self):
        pricing = client.post("/ledger", json=JANE_PAYLOAD).json()["pricing"]
        for field in ("pricing_label", "gross_margin", "gross_margin_percent"):
            assert field in pricing

    def test_family_friend_pricing_mode(self):
        payload = {
            **JANE_PAYLOAD,
            "treatment_plan": "Forehead Lines: 32 units",
            "pricing_mode": "family-friend",
            "client_charge": None,
        }
        data = client.post("/ledger", json=payload).json()
        assert data["pricing"]["recommended_charge"] == 320.0  # 32 units * $10

    def test_semicolon_separator_accepted(self):
        payload = {**JANE_PAYLOAD, "treatment_plan": "Forehead: 8 units;Frown Lines: 12 units"}
        resp = client.post("/ledger", json=payload)
        assert resp.status_code == 200
        assert resp.json()["total_units"] == 20.0

    def test_invalid_diluent_returns_422(self):
        payload = {**JANE_PAYLOAD, "diluent": "not a measurement"}
        resp = client.post("/ledger", json=payload)
        assert resp.status_code == 422

    def test_mg_units_rejected_with_422(self):
        payload = {**JANE_PAYLOAD, "treatment_plan": "Forehead: 8 mg"}
        resp = client.post("/ledger", json=payload)
        assert resp.status_code == 422

    def test_negative_units_rejected_with_422(self):
        payload = {**JANE_PAYLOAD, "treatment_plan": "Forehead: -5 units"}
        resp = client.post("/ledger", json=payload)
        assert resp.status_code == 422

    def test_custom_mode_without_price_returns_422(self):
        # client_charge must also be None so the pricing mode branch is actually evaluated
        payload = {**JANE_PAYLOAD, "pricing_mode": "custom", "custom_price": None, "client_charge": None}
        resp = client.post("/ledger", json=payload)
        assert resp.status_code == 422

    def test_missing_required_field_returns_422(self):
        payload = {k: v for k, v in JANE_PAYLOAD.items() if k != "client"}
        resp = client.post("/ledger", json=payload)
        assert resp.status_code == 422
