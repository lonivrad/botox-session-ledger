"""
Tests for botox_session_ledger.py

Covers:
- All parsing functions (parse_diluent, parse_money, parse_custom_price, parse_treatment_plan)
- calculate_syringes_required (including the documented bug-fix case)
- calculate_costs
- calculate_pricing (all three modes)
- build_ledger integration tests (all four README test cases + edge cases)
- build_ledger_data and ledger_to_dict (JSON output)
"""

import json

import pytest

from botox_session_ledger import (
    DEFAULT_VIAL_COST,
    FAMILY_FRIEND_PRICE_PER_UNIT,
    VIAL_UNITS,
    InvalidDiluentError,
    InvalidMoneyError,
    InvalidPricingError,
    InvalidTreatmentPlanError,
    build_ledger,
    build_ledger_data,
    calculate_costs,
    calculate_pricing,
    calculate_syringes_required,
    ledger_to_dict,
    parse_custom_price,
    parse_diluent,
    parse_money,
    parse_treatment_plan,
)

# ─────────────────────────────────────────────
# parse_diluent
# ─────────────────────────────────────────────


class TestParseDiluent:
    def test_standard_decimal(self):
        assert parse_diluent("2.5 mL") == 2.5

    def test_integer_value(self):
        assert parse_diluent("1 mL") == 1.0

    def test_case_insensitive(self):
        assert parse_diluent("2.5 ML") == 2.5

    def test_no_space_before_unit(self):
        assert parse_diluent("2.5mL") == 2.5

    def test_missing_ml_raises(self):
        with pytest.raises(InvalidDiluentError, match="mL"):
            parse_diluent("2.5")

    def test_zero_raises(self):
        with pytest.raises(InvalidDiluentError, match="greater than zero"):
            parse_diluent("0 mL")

    def test_non_numeric_raises(self):
        with pytest.raises(InvalidDiluentError):
            parse_diluent("two mL")


# ─────────────────────────────────────────────
# parse_money
# ─────────────────────────────────────────────


class TestParseMoney:
    def test_dollar_sign(self):
        assert parse_money("$420") == 420.0

    def test_no_dollar_sign(self):
        assert parse_money("420") == 420.0

    def test_with_comma(self):
        assert parse_money("$1,200") == 1200.0

    def test_decimal(self):
        assert parse_money("$42.50") == 42.50

    def test_none_returns_none(self):
        assert parse_money(None) is None

    def test_negative_raises(self):
        with pytest.raises(InvalidMoneyError, match="negative"):
            parse_money("-50")

    def test_invalid_string_raises(self):
        with pytest.raises(InvalidMoneyError):
            parse_money("abc")


# ─────────────────────────────────────────────
# parse_custom_price
# ─────────────────────────────────────────────


class TestParseCustomPrice:
    def test_plain_number(self):
        assert parse_custom_price("12") == 12.0

    def test_dollar_per_unit(self):
        assert parse_custom_price("$12/unit") == 12.0

    def test_per_unit_text(self):
        assert parse_custom_price("12 per unit") == 12.0

    def test_none_returns_none(self):
        assert parse_custom_price(None) is None

    def test_zero_raises(self):
        with pytest.raises(InvalidPricingError, match="greater than zero"):
            parse_custom_price("0")

    def test_negative_raises(self):
        with pytest.raises(InvalidPricingError):
            parse_custom_price("-5")

    def test_invalid_string_raises(self):
        with pytest.raises(InvalidPricingError):
            parse_custom_price("abc")


# ─────────────────────────────────────────────
# parse_treatment_plan
# ─────────────────────────────────────────────


class TestParseTreatmentPlan:
    CONCENTRATION = 40.0  # 100 units / 2.5 mL

    def test_single_area(self):
        entries = parse_treatment_plan("Forehead Lines: 8 units", self.CONCENTRATION)
        assert len(entries) == 1
        assert entries[0].area == "Forehead Lines"
        assert entries[0].units == 8.0
        assert pytest.approx(entries[0].volume_ml, rel=1e-4) == 0.2

    def test_multiple_areas(self):
        plan = "Forehead Lines: 8 units\nFrown Lines: 12 units"
        entries = parse_treatment_plan(plan, self.CONCENTRATION)
        assert len(entries) == 2
        assert entries[0].units == 8.0
        assert entries[1].units == 12.0

    def test_each_side_doubles_units(self):
        entries = parse_treatment_plan("Masseters: 20 units each side", self.CONCENTRATION)
        assert entries[0].units == 40.0
        assert "(total both sides)" in entries[0].area

    def test_per_side_doubles_units(self):
        entries = parse_treatment_plan("Crow's Feet: 6 units per side", self.CONCENTRATION)
        assert entries[0].units == 12.0

    def test_u100_markings_correct(self):
        entries = parse_treatment_plan("Forehead: 8 units", self.CONCENTRATION)
        # 8 units / 40 units/mL = 0.2 mL → 20 U-100 markings
        assert pytest.approx(entries[0].u100_markings, rel=1e-4) == 20.0

    def test_mg_raises(self):
        with pytest.raises(InvalidTreatmentPlanError, match="mg"):
            parse_treatment_plan("Forehead: 8 mg", self.CONCENTRATION)

    def test_mcg_raises(self):
        with pytest.raises(InvalidTreatmentPlanError, match="mcg"):
            parse_treatment_plan("Forehead: 8 mcg", self.CONCENTRATION)

    def test_negative_units_raises(self):
        with pytest.raises(InvalidTreatmentPlanError, match="greater than zero"):
            parse_treatment_plan("Forehead: -8 units", self.CONCENTRATION)

    def test_zero_units_raises(self):
        with pytest.raises(InvalidTreatmentPlanError, match="greater than zero"):
            parse_treatment_plan("Forehead: 0 units", self.CONCENTRATION)

    def test_missing_colon_raises(self):
        with pytest.raises(InvalidTreatmentPlanError, match="Invalid treatment line"):
            parse_treatment_plan("Forehead 8 units", self.CONCENTRATION)

    def test_empty_plan_raises(self):
        with pytest.raises(InvalidTreatmentPlanError, match="required"):
            parse_treatment_plan("", self.CONCENTRATION)


# ─────────────────────────────────────────────
# calculate_syringes_required
# ─────────────────────────────────────────────


class TestCalculateSyringesRequired:
    def test_one_area(self):
        assert calculate_syringes_required(1) == 1

    def test_two_areas(self):
        assert calculate_syringes_required(2) == 1

    def test_three_areas_documented_bug_fix(self):
        # README documents: Jane has 3 areas → 2 syringes (not 5 from the old broken logic)
        assert calculate_syringes_required(3) == 2

    def test_four_areas(self):
        assert calculate_syringes_required(4) == 2

    def test_five_areas(self):
        assert calculate_syringes_required(5) == 3

    def test_six_areas(self):
        assert calculate_syringes_required(6) == 3


# ─────────────────────────────────────────────
# calculate_costs
# ─────────────────────────────────────────────


class TestCalculateCosts:
    def test_60_units_3_areas(self):
        # Jane: 60 units, 60% of vial, 3 treatment areas
        vial_pct = 60 / VIAL_UNITS
        costs = calculate_costs(vial_percent_used=vial_pct, treatment_area_count=3)

        assert pytest.approx(costs.botox_product_cost_used, rel=1e-4) == DEFAULT_VIAL_COST * 0.6
        assert costs.syringes_required == 2
        assert costs.prep_pads_low == 3
        assert costs.prep_pads_high == 6
        assert costs.total_session_cost_low < costs.total_session_cost_high
        assert costs.total_session_cost_mid == pytest.approx(
            (costs.total_session_cost_low + costs.total_session_cost_high) / 2
        )

    def test_full_vial(self):
        costs = calculate_costs(vial_percent_used=1.0, treatment_area_count=2)
        assert pytest.approx(costs.botox_product_cost_used, rel=1e-4) == DEFAULT_VIAL_COST

    def test_minimum_one_syringe(self):
        costs = calculate_costs(vial_percent_used=0.1, treatment_area_count=1)
        assert costs.syringes_required == 1

    def test_cost_components_sum_correctly(self):
        costs = calculate_costs(vial_percent_used=0.5, treatment_area_count=4)
        expected_low = (
            costs.botox_product_cost_used
            + costs.syringe_cost_total
            + costs.prep_pad_cost_low
            + costs.glove_cost_total
            + costs.saline_cost_allocated
        )
        assert pytest.approx(costs.total_session_cost_low, rel=1e-6) == expected_low


# ─────────────────────────────────────────────
# calculate_pricing
# ─────────────────────────────────────────────


class TestCalculatePricing:
    SESSION_COST_MID = 397.11  # approximate for Jane (60 units, 2.5 mL)

    def test_standard_pricing_achieves_target_margin(self):
        pricing = calculate_pricing(
            total_units=60,
            total_session_cost_mid=self.SESSION_COST_MID,
            pricing_mode="standard",
            client_charge=None,
            custom_price=None,
        )
        assert pricing.gross_margin_percent == pytest.approx(20.0, rel=0.01)

    def test_family_friend_pricing(self):
        pricing = calculate_pricing(
            total_units=32,
            total_session_cost_mid=200.0,
            pricing_mode="family-friend",
            client_charge=None,
            custom_price=None,
        )
        assert pricing.recommended_charge == 320.0  # 32 * $10
        assert pricing.recommended_per_unit == FAMILY_FRIEND_PRICE_PER_UNIT
        assert "Family-friend" in pricing.pricing_label

    def test_custom_pricing(self):
        pricing = calculate_pricing(
            total_units=40,
            total_session_cost_mid=200.0,
            pricing_mode="custom",
            client_charge=None,
            custom_price="$15/unit",
        )
        assert pricing.recommended_charge == 600.0  # 40 * $15
        assert pricing.recommended_per_unit == 15.0

    def test_actual_charge_overrides_recommended(self):
        pricing = calculate_pricing(
            total_units=60,
            total_session_cost_mid=self.SESSION_COST_MID,
            pricing_mode="standard",
            client_charge="$420",
            custom_price=None,
        )
        assert pricing.actual_client_charge == 420.0
        assert pricing.recommended_charge is None

    def test_gross_margin_calculation(self):
        pricing = calculate_pricing(
            total_units=60,
            total_session_cost_mid=self.SESSION_COST_MID,
            pricing_mode="standard",
            client_charge="$420",
            custom_price=None,
        )
        assert pricing.gross_margin == pytest.approx(420 - self.SESSION_COST_MID, rel=1e-4)
        assert pricing.gross_margin_percent == pytest.approx(
            (420 - self.SESSION_COST_MID) / 420 * 100, rel=1e-4
        )

    def test_custom_mode_without_price_raises(self):
        with pytest.raises(InvalidPricingError, match="custom-price"):
            calculate_pricing(
                total_units=40,
                total_session_cost_mid=200.0,
                pricing_mode="custom",
                client_charge=None,
                custom_price=None,
            )

    def test_invalid_pricing_mode_raises(self):
        with pytest.raises(InvalidPricingError, match="Pricing mode"):
            calculate_pricing(
                total_units=40,
                total_session_cost_mid=200.0,
                pricing_mode="discount",
                client_charge=None,
                custom_price=None,
            )


# ─────────────────────────────────────────────
# build_ledger — integration tests
# ─────────────────────────────────────────────


class TestBuildLedger:
    # Jane's treatment plan from README Test 1
    JANE_PLAN = (
        "Forehead Lines: 8 units\n"
        "Frown Lines: 12 units\n"
        "Masseters: 20 units each side"
    )

    def test_jane_total_units(self):
        """README Test 1: Jane → 60 total units (8 + 12 + 20*2)."""
        ledger = build_ledger(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
            client_charge="$420",
        )
        assert "60" in ledger

    def test_jane_total_volume(self):
        """README Test 1: Jane → 1.50 mL total volume."""
        ledger = build_ledger(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
            client_charge="$420",
        )
        assert "1.50 mL" in ledger

    def test_jane_vial_remaining(self):
        """README Test 1: Jane → 40 units remaining."""
        ledger = build_ledger(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
            client_charge="$420",
        )
        assert "40" in ledger

    def test_jane_gross_margin(self):
        """README Test 1: Jane at $420 → ~5.5% gross margin."""
        ledger = build_ledger(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
            client_charge="$420",
        )
        assert "5.5%" in ledger

    def test_family_friend_recommended_charge(self):
        """README Test 2: Sarah, family-friend → $320 recommended charge (32 units × $10)."""
        plan = "Crow's Feet: 10 units each side\nFrown Lines: 12 units"
        ledger = build_ledger(
            client="Sarah",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=plan,
            pricing_mode="family-friend",
        )
        assert "Family-friend" in ledger
        assert "$320.00" in ledger

    def test_different_reconstitution_changes_concentration(self):
        """README Test 4: Emily, 1.0 mL → concentration 100 units/mL."""
        ledger = build_ledger(
            client="Emily",
            product="Botox",
            diluent_text="1.0 mL",
            treatment_plan="Forehead Lines: 8 units",
            pricing_mode="standard",
        )
        assert "100 units/mL" in ledger

    def test_over_vial_triggers_warning(self):
        """Using more than 100 units should produce an inventory warning flag."""
        ledger = build_ledger(
            client="Test",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan="Area A: 60 units\nArea B: 60 units",
            pricing_mode="standard",
        )
        assert "exceeds the 100-unit vial" in ledger

    def test_non_botox_product_triggers_warning(self):
        """Non-Botox product name should produce a product warning flag."""
        ledger = build_ledger(
            client="Test",
            product="Dysport",
            diluent_text="2.5 mL",
            treatment_plan="Forehead: 8 units",
            pricing_mode="standard",
        )
        assert "Dysport" in ledger
        assert "designed around" in ledger

    def test_standard_disclaimer_flags_always_present(self):
        """Core disclaimer flags must appear in every ledger."""
        ledger = build_ledger(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan="Forehead: 8 units",
            pricing_mode="standard",
        )
        assert "Dose values were user-provided." in ledger
        assert "does not validate clinical appropriateness" in ledger

    def test_semicolon_separator_parsed_correctly(self):
        """Semicolons in treatment plan (CLI usage) should be treated as newlines."""
        ledger = build_ledger(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan="Forehead Lines: 8 units;Frown Lines: 12 units",
            pricing_mode="standard",
        )
        # Both areas parsed → 20 total units
        assert "20" in ledger


# ─────────────────────────────────────────────
# build_ledger_data + ledger_to_dict (JSON output)
# ─────────────────────────────────────────────


class TestJSONOutput:
    JANE_PLAN = (
        "Forehead Lines: 8 units\n"
        "Frown Lines: 12 units\n"
        "Masseters: 20 units each side"
    )

    def test_build_ledger_data_returns_ledger_data(self):
        from botox_session_ledger import LedgerData
        data = build_ledger_data(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
            client_charge="$420",
        )
        assert isinstance(data, LedgerData)

    def test_ledger_to_dict_is_json_serializable(self):
        data = build_ledger_data(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
            client_charge="$420",
        )
        result = ledger_to_dict(data)
        # Should not raise
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

    def test_dict_contains_top_level_keys(self):
        data = build_ledger_data(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
        )
        result = ledger_to_dict(data)
        for key in ("client", "product", "diluent_ml", "concentration", "entries", "costs", "pricing", "flags"):
            assert key in result

    def test_dict_entries_are_list_of_dicts(self):
        data = build_ledger_data(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
        )
        result = ledger_to_dict(data)
        assert isinstance(result["entries"], list)
        assert all(isinstance(e, dict) for e in result["entries"])

    def test_dict_total_units_correct(self):
        data = build_ledger_data(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
        )
        assert ledger_to_dict(data)["total_units"] == 60.0

    def test_dict_nested_costs_preserved(self):
        data = build_ledger_data(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
        )
        result = ledger_to_dict(data)
        assert "botox_product_cost_used" in result["costs"]
        assert "total_session_cost_mid" in result["costs"]

    def test_dict_nested_pricing_preserved(self):
        data = build_ledger_data(
            client="Jane",
            product="Botox",
            diluent_text="2.5 mL",
            treatment_plan=self.JANE_PLAN,
            pricing_mode="standard",
            client_charge="$420",
        )
        result = ledger_to_dict(data)
        assert result["pricing"]["actual_client_charge"] == 420.0
        assert result["pricing"]["gross_margin_percent"] is not None
