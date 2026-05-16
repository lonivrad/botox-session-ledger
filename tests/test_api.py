"""
HTTP contract tests for the FastAPI ledger endpoint.

These tests verify the API surface: status codes, response shape, and
error handling. Numeric correctness of the ledger calculation is already
covered by the unit tests in test_ledger.py — don't duplicate it here.
"""

import os
import sys

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
        assert client.get("/health").status_code == 200

    def test_returns_ok_status(self):
        assert client.get("/health").json() == {"status": "ok"}


class TestLedgerResponseShape:
    """Verify the API returns JSON with the documented top-level structure."""

    def test_valid_request_returns_200(self):
        assert client.post("/ledger", json=JANE_PAYLOAD).status_code == 200

    def test_content_type_is_json(self):
        resp = client.post("/ledger", json=JANE_PAYLOAD)
        assert "application/json" in resp.headers["content-type"]

    def test_top_level_fields_present(self):
        data = client.post("/ledger", json=JANE_PAYLOAD).json()
        for field in ("client", "product", "diluent_ml", "concentration",
                      "entries", "costs", "pricing", "flags", "total_units",
                      "total_volume_ml"):
            assert field in data, f"Missing top-level field: {field}"

    def test_entries_are_list_of_objects(self):
        entries = client.post("/ledger", json=JANE_PAYLOAD).json()["entries"]
        assert isinstance(entries, list) and len(entries) > 0
        for field in ("area", "units", "volume_ml", "u100_markings"):
            assert field in entries[0], f"Missing entry field: {field}"

    def test_costs_object_has_required_fields(self):
        costs = client.post("/ledger", json=JANE_PAYLOAD).json()["costs"]
        for field in ("botox_product_cost_used", "syringes_required",
                      "total_session_cost_low", "total_session_cost_high",
                      "total_session_cost_mid"):
            assert field in costs, f"Missing costs field: {field}"

    def test_pricing_object_has_required_fields(self):
        pricing = client.post("/ledger", json=JANE_PAYLOAD).json()["pricing"]
        for field in ("pricing_label", "gross_margin", "gross_margin_percent"):
            assert field in pricing, f"Missing pricing field: {field}"

    def test_flags_is_a_list_of_strings(self):
        flags = client.post("/ledger", json=JANE_PAYLOAD).json()["flags"]
        assert isinstance(flags, list)
        assert all(isinstance(f, str) for f in flags)


class TestLedgerErrorHandling:
    """Verify the API rejects bad inputs with 422 and useful error details."""

    def test_missing_required_field_client(self):
        payload = {k: v for k, v in JANE_PAYLOAD.items() if k != "client"}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_missing_required_field_diluent(self):
        payload = {k: v for k, v in JANE_PAYLOAD.items() if k != "diluent"}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_invalid_diluent_format(self):
        payload = {**JANE_PAYLOAD, "diluent": "two tablespoons"}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_mg_units_rejected(self):
        payload = {**JANE_PAYLOAD, "treatment_plan": "Forehead: 8 mg"}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_negative_units_rejected(self):
        payload = {**JANE_PAYLOAD, "treatment_plan": "Forehead: -5 units"}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_invalid_treatment_plan_format(self):
        payload = {**JANE_PAYLOAD, "treatment_plan": "no colon here 8 units"}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_custom_mode_without_price(self):
        payload = {**JANE_PAYLOAD, "pricing_mode": "custom",
                   "custom_price": None, "client_charge": None}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_unknown_pricing_mode_without_charge(self):
        # pricing_mode is only validated when no client_charge is provided —
        # if a charge is given explicitly the mode is irrelevant and skipped.
        payload = {**JANE_PAYLOAD, "pricing_mode": "discount", "client_charge": None}
        assert client.post("/ledger", json=payload).status_code == 422

    def test_semicolon_separator_accepted(self):
        """Semicolons as area separators are valid (CLI convenience format)."""
        payload = {**JANE_PAYLOAD,
                   "treatment_plan": "Forehead: 8 units;Frown Lines: 12 units"}
        assert client.post("/ledger", json=payload).status_code == 200
