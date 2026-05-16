#!/usr/bin/env python3

import argparse
import dataclasses
import json
import math
import re
from dataclasses import dataclass
from typing import List, Optional

# -----------------------------
# Custom exceptions
# -----------------------------

class BotoxLedgerError(ValueError):
    """Base exception for all botox-session-ledger validation errors."""


class InvalidDiluentError(BotoxLedgerError):
    """Raised when the diluent input is missing, malformed, or non-positive."""


class InvalidTreatmentPlanError(BotoxLedgerError):
    """Raised when the treatment plan has a missing, malformed, or invalid entry."""


class InvalidPricingError(BotoxLedgerError):
    """Raised when a pricing mode is unrecognized or required pricing inputs are absent."""


class InvalidMoneyError(BotoxLedgerError):
    """Raised when a money value (client charge, custom price) is malformed or negative."""


# -----------------------------
# Default Botox assumptions
# -----------------------------

VIAL_UNITS = 100
DEFAULT_VIAL_COST = 656.00
DEFAULT_SALINE_COST_PER_VIAL = 5.20

SYRINGE_PACKAGE_COST = 18.00
SYRINGES_PER_PACKAGE = 100
SYRINGE_COST = SYRINGE_PACKAGE_COST / SYRINGES_PER_PACKAGE

ALCOHOL_PAD_COST = 0.002
GLOVE_COST = 0.010
GLOVES_PER_SESSION = 2

FAMILY_FRIEND_PRICE_PER_UNIT = 10.00
DEFAULT_TARGET_MARGIN = 0.20

PRACTICAL_VOLUME_WARNING_THRESHOLD_ML = 0.01


# -----------------------------
# Data models
# -----------------------------

@dataclass
class TreatmentEntry:
    area: str
    units: float
    volume_ml: float
    u100_markings: float


@dataclass
class SessionCosts:
    botox_product_cost_used: float
    saline_cost_allocated: float
    syringes_required: int
    syringe_cost_total: float
    prep_pads_low: int
    prep_pads_high: int
    prep_pad_cost_low: float
    prep_pad_cost_high: float
    glove_cost_total: float
    consumables_low: float
    consumables_high: float
    total_session_cost_low: float
    total_session_cost_high: float
    total_session_cost_mid: float


@dataclass
class PricingResult:
    pricing_label: str
    recommended_charge: Optional[float]
    recommended_per_unit: Optional[float]
    actual_client_charge: Optional[float]
    gross_margin: Optional[float]
    gross_margin_percent: Optional[float]


@dataclass
class LedgerData:
    """Structured representation of a complete session ledger."""
    client: str
    product: str
    diluent_ml: float
    concentration: float
    entries: List[TreatmentEntry]
    total_units: float
    total_volume_ml: float
    total_u100_markings: float
    expected_remaining_units: float
    vial_percent_used: float
    costs: SessionCosts
    pricing: PricingResult
    flags: List[str]


# -----------------------------
# Parsing helpers
# -----------------------------

def parse_diluent(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)\s*mL\b", text, re.IGNORECASE)

    if not match:
        raise InvalidDiluentError("Diluent must be provided in mL. Example: '2.5 mL'.")

    diluent = float(match.group(1))

    if diluent <= 0:
        raise InvalidDiluentError("Diluent amount must be greater than zero.")

    return diluent


def parse_money(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None

    cleaned = value.replace("$", "").replace(",", "").strip()

    try:
        amount = float(cleaned)
    except ValueError:
        raise InvalidMoneyError(f"Invalid money value: {value}")

    if amount < 0:
        raise InvalidMoneyError("Money values cannot be negative.")

    return amount


def parse_custom_price(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None

    cleaned = (
        value.lower()
        .replace("$", "")
        .replace("/unit", "")
        .replace("per unit", "")
        .strip()
    )

    try:
        price = float(cleaned)
    except ValueError:
        raise InvalidPricingError("Custom price must be numeric. Example: '12' or '$12/unit'.")

    if price <= 0:
        raise InvalidPricingError("Custom price per unit must be greater than zero.")

    return price


def parse_treatment_plan(plan_text: str, concentration: float) -> List[TreatmentEntry]:
    """
    Parses treatment plan lines like:
    Forehead Lines: 8 units
    Frown Lines: 12 units
    Crow's Feet: 6 units each side
    Masseters: 20 units each side

    For "each side", "per side", or "each masseter", units are doubled.
    """

    if not plan_text.strip():
        raise InvalidTreatmentPlanError("Treatment plan is required.")

    entries: List[TreatmentEntry] = []
    lines = [line.strip() for line in plan_text.splitlines() if line.strip()]

    for line in lines:
        if ":" not in line:
            raise InvalidTreatmentPlanError(
                f"Invalid treatment line: '{line}'. Expected format like 'Forehead Lines: 8 units'."
            )

        area, detail = line.split(":", 1)
        area = area.strip()
        detail = detail.strip()

        if not area:
            raise InvalidTreatmentPlanError(f"Missing treatment area in line: '{line}'.")

        if re.search(r"\bmg\b|\bmcg\b", detail, re.IGNORECASE):
            raise InvalidTreatmentPlanError(
                f"Invalid unit in line '{line}'. Botox treatment plans must use units, not mg or mcg."
            )

        number_match = re.search(r"(-?\d+(?:\.\d+)?)\s*units?\b", detail, re.IGNORECASE)

        if not number_match:
            raise InvalidTreatmentPlanError(
                f"Invalid or missing units in line '{line}'. Expected format like '8 units'."
            )

        units = float(number_match.group(1))

        if units <= 0:
            raise InvalidTreatmentPlanError(f"Treatment units must be greater than zero in line: '{line}'.")

        if re.search(r"\beach side\b|\bper side\b|\beach masseter\b", detail, re.IGNORECASE):
            units *= 2
            area = f"{area} (total both sides)"

        volume_ml = units / concentration
        u100_markings = volume_ml * 100

        entries.append(
            TreatmentEntry(
                area=area,
                units=units,
                volume_ml=volume_ml,
                u100_markings=u100_markings,
            )
        )

    return entries


# -----------------------------
# Calculation functions
# -----------------------------

def calculate_syringes_required(treatment_area_count: int) -> int:
    """
    Operational estimate: 1 syringe per 1-2 treatment areas.
    3-4 areas = 2 syringes, 5-6 areas = 3 syringes, etc.

    This avoids incorrectly treating U-100 syringe markings as Botox units.
    """
    return max(1, math.ceil(treatment_area_count / 2))


def calculate_costs(vial_percent_used: float, treatment_area_count: int) -> SessionCosts:
    """
    Calculates all operational costs for a session based on vial usage and treatment areas.
    """
    syringes_required = calculate_syringes_required(treatment_area_count)
    syringe_cost_total = syringes_required * SYRINGE_COST

    prep_pads_low = treatment_area_count
    prep_pads_high = treatment_area_count * 2
    prep_pad_cost_low = prep_pads_low * ALCOHOL_PAD_COST
    prep_pad_cost_high = prep_pads_high * ALCOHOL_PAD_COST

    glove_cost_total = GLOVES_PER_SESSION * GLOVE_COST
    botox_product_cost_used = DEFAULT_VIAL_COST * vial_percent_used
    saline_cost_allocated = DEFAULT_SALINE_COST_PER_VIAL * vial_percent_used

    consumables_low = syringe_cost_total + prep_pad_cost_low + glove_cost_total + saline_cost_allocated
    consumables_high = syringe_cost_total + prep_pad_cost_high + glove_cost_total + saline_cost_allocated

    total_session_cost_low = botox_product_cost_used + consumables_low
    total_session_cost_high = botox_product_cost_used + consumables_high
    total_session_cost_mid = (total_session_cost_low + total_session_cost_high) / 2

    return SessionCosts(
        botox_product_cost_used=botox_product_cost_used,
        saline_cost_allocated=saline_cost_allocated,
        syringes_required=syringes_required,
        syringe_cost_total=syringe_cost_total,
        prep_pads_low=prep_pads_low,
        prep_pads_high=prep_pads_high,
        prep_pad_cost_low=prep_pad_cost_low,
        prep_pad_cost_high=prep_pad_cost_high,
        glove_cost_total=glove_cost_total,
        consumables_low=consumables_low,
        consumables_high=consumables_high,
        total_session_cost_low=total_session_cost_low,
        total_session_cost_high=total_session_cost_high,
        total_session_cost_mid=total_session_cost_mid,
    )


def calculate_pricing(
    total_units: float,
    total_session_cost_mid: float,
    pricing_mode: str,
    client_charge: Optional[str],
    custom_price: Optional[str],
) -> PricingResult:
    """
    Calculates recommended pricing and gross margin based on pricing mode and session costs.
    """
    pricing_mode_clean = pricing_mode.strip().lower().replace("_", "-") if pricing_mode else "standard"
    actual_client_charge = parse_money(client_charge)
    custom_price_per_unit = parse_custom_price(custom_price)

    recommended_charge: Optional[float] = None
    recommended_per_unit: Optional[float] = None

    if actual_client_charge is None:
        if pricing_mode_clean in ["family-friend", "family friend", "friend", "family"]:
            recommended_per_unit = FAMILY_FRIEND_PRICE_PER_UNIT
            recommended_charge = total_units * recommended_per_unit
            pricing_label = "Family-friend pricing"
        elif pricing_mode_clean == "custom":
            if custom_price_per_unit is None:
                raise InvalidPricingError(
                    "Custom pricing mode requires --custom-price. Example: --custom-price '$12/unit'."
                )
            recommended_per_unit = custom_price_per_unit
            recommended_charge = total_units * recommended_per_unit
            pricing_label = "Custom per-unit pricing"
        elif pricing_mode_clean == "standard":
            recommended_charge = total_session_cost_mid / (1 - DEFAULT_TARGET_MARGIN)
            recommended_per_unit = recommended_charge / total_units if total_units > 0 else 0
            pricing_label = "Standard target-margin pricing"
        else:
            raise InvalidPricingError("Pricing mode must be one of: standard, family-friend, custom.")
    else:
        pricing_label = "Actual client charge provided"

    charge_for_margin = actual_client_charge if actual_client_charge is not None else recommended_charge

    gross_margin: Optional[float] = None
    gross_margin_percent: Optional[float] = None

    if charge_for_margin is not None:
        gross_margin = charge_for_margin - total_session_cost_mid
        gross_margin_percent = (gross_margin / charge_for_margin) * 100 if charge_for_margin > 0 else 0

    return PricingResult(
        pricing_label=pricing_label,
        recommended_charge=recommended_charge,
        recommended_per_unit=recommended_per_unit,
        actual_client_charge=actual_client_charge,
        gross_margin=gross_margin,
        gross_margin_percent=gross_margin_percent,
    )


# -----------------------------
# Orchestrator
# -----------------------------

def build_ledger_data(
    client: str,
    product: str,
    diluent_text: str,
    treatment_plan: str,
    pricing_mode: str = "standard",
    client_charge: Optional[str] = None,
    custom_price: Optional[str] = None,
) -> LedgerData:
    """
    Parses inputs, runs all calculations, and returns structured LedgerData.
    Use this when you need the data (API, JSON output, downstream processing).
    For a formatted text report, use build_ledger().
    """
    product_clean = product.strip() if product else "Botox"

    product_warning = None
    if product_clean.lower() != "botox":
        product_warning = (
            f"Product entered as '{product_clean}'. This skill is designed around "
            "Botox 100-unit vial assumptions."
        )

    diluent_ml = parse_diluent(diluent_text)
    concentration = VIAL_UNITS / diluent_ml

    entries = parse_treatment_plan(treatment_plan, concentration)

    total_units = sum(entry.units for entry in entries)
    total_volume_ml = sum(entry.volume_ml for entry in entries)
    total_u100_markings = total_volume_ml * 100
    expected_remaining_units = VIAL_UNITS - total_units
    vial_percent_used = total_units / VIAL_UNITS
    treatment_area_count = len(entries)

    costs = calculate_costs(vial_percent_used, treatment_area_count)
    pricing = calculate_pricing(
        total_units, costs.total_session_cost_mid, pricing_mode, client_charge, custom_price
    )

    flags = [
        "Dose values were user-provided.",
        "This skill does not validate clinical appropriateness.",
        "Pricing estimates do not represent final profitability.",
        "Pricing does not include malpractice insurance, provider compensation, rent, taxes, merchant fees, payroll, marketing, licensing, spoilage, or other fixed operating expenses.",
        "1 mL = 1 cc. U-100 syringe markings are not cc.",
    ]

    if product_warning:
        flags.append(product_warning)

    if expected_remaining_units < 0:
        flags.append("Warning: planned treatment exceeds the 100-unit vial inventory.")

    for entry in entries:
        if entry.volume_ml < PRACTICAL_VOLUME_WARNING_THRESHOLD_ML:
            flags.append(
                f"Warning: {entry.area} volume is below {PRACTICAL_VOLUME_WARNING_THRESHOLD_ML} mL and may be impractical to measure accurately."
            )

    return LedgerData(
        client=client,
        product=product_clean,
        diluent_ml=diluent_ml,
        concentration=concentration,
        entries=entries,
        total_units=total_units,
        total_volume_ml=total_volume_ml,
        total_u100_markings=total_u100_markings,
        expected_remaining_units=expected_remaining_units,
        vial_percent_used=vial_percent_used,
        costs=costs,
        pricing=pricing,
        flags=flags,
    )


def ledger_to_dict(data: LedgerData) -> dict:
    """Converts LedgerData to a JSON-serializable dict via dataclasses.asdict()."""
    return dataclasses.asdict(data)


# -----------------------------
# Formatting
# -----------------------------

def format_money(amount: float) -> str:
    return f"${amount:,.2f}"


def format_number(value: float, digits: int = 2) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def format_ledger(data: LedgerData) -> str:
    """Formats a LedgerData object as a human-readable text report."""
    output = []

    output.append("Botox Session Ledger")
    output.append("")
    output.append(f"Client: {data.client}")
    output.append(f"Product: {data.product}")
    output.append(f"Vial assumption: {VIAL_UNITS} units")
    output.append(f"Diluent: {format_number(data.diluent_ml)} mL")
    output.append(f"Concentration: {format_number(data.concentration)} units/mL")
    output.append("")
    output.append("Dilution arithmetic:")
    output.append(
        f"{VIAL_UNITS} units ÷ {format_number(data.diluent_ml)} mL = {format_number(data.concentration)} units/mL"
    )
    output.append("")
    output.append("Treatment Plan")
    output.append("")
    output.append("| Area | Units | Arithmetic | Volume | U-100 |")
    output.append("|---|---:|---|---:|---:|")

    for entry in data.entries:
        arithmetic = f"{format_number(entry.units)} ÷ {format_number(data.concentration)}"
        volume = f"{entry.volume_ml:.2f} mL / {entry.volume_ml:.2f} cc"
        u100 = f"{entry.u100_markings:.0f}"
        output.append(
            f"| {entry.area} | {format_number(entry.units)} | {arithmetic} | {volume} | {u100} |"
        )

    output.append("")
    output.append("Treatment summary:")
    output.append("")
    output.append(f"Total planned dose: {format_number(data.total_units)} units")
    output.append("")
    output.append(f"Total volume: {data.total_volume_ml:.2f} mL / {data.total_volume_ml:.2f} cc")
    output.append("")
    output.append(f"Total U-100 syringe markings: {data.total_u100_markings:.0f}")
    output.append("")
    output.append(f"Expected vial remaining: {format_number(data.expected_remaining_units)} units")
    output.append("")
    output.append(f"Vial used: {data.vial_percent_used * 100:.1f}%")
    output.append("")
    output.append("Financial summary:")
    output.append("")
    output.append(f"Product cost used: {format_money(data.costs.botox_product_cost_used)}")
    output.append("")
    output.append(f"Saline allocation: {format_money(data.costs.saline_cost_allocated)}")
    output.append("")
    output.append(f"Syringes required: {data.costs.syringes_required}")
    output.append("")
    output.append(f"Syringe cost: {format_money(data.costs.syringe_cost_total)}")
    output.append("")
    output.append(f"Prep pads estimated: {data.costs.prep_pads_low}–{data.costs.prep_pads_high}")
    output.append("")
    output.append(
        f"Prep pad cost: {format_money(data.costs.prep_pad_cost_low)}–{format_money(data.costs.prep_pad_cost_high)}"
    )
    output.append("")
    output.append(f"Glove cost: {format_money(data.costs.glove_cost_total)}")
    output.append("")
    output.append(
        f"Consumables: {format_money(data.costs.consumables_low)}–{format_money(data.costs.consumables_high)}"
    )
    output.append("")
    output.append(
        f"Total session cost: {format_money(data.costs.total_session_cost_low)}–{format_money(data.costs.total_session_cost_high)}"
    )
    output.append("")
    output.append("Pricing summary:")
    output.append("")
    output.append(f"Pricing mode: {data.pricing.pricing_label}")
    output.append("")

    if data.pricing.actual_client_charge is not None:
        output.append(f"Client charge: {format_money(data.pricing.actual_client_charge)}")
    else:
        output.append(f"Recommended charge: {format_money(data.pricing.recommended_charge)}")
        output.append("")
        output.append(
            f"Recommended per-unit price: {format_money(data.pricing.recommended_per_unit)}/unit"
        )

    output.append("")

    if data.pricing.gross_margin is not None and data.pricing.gross_margin_percent is not None:
        output.append(f"Gross margin: {format_money(data.pricing.gross_margin)}")
        output.append("")
        output.append(f"Gross margin %: {data.pricing.gross_margin_percent:.1f}%")
        output.append("")

    output.append("Flags:")
    output.append("")

    for flag in data.flags:
        output.append(f"- {flag}")

    return "\n".join(output)


def build_ledger(
    client: str,
    product: str,
    diluent_text: str,
    treatment_plan: str,
    pricing_mode: str = "standard",
    client_charge: Optional[str] = None,
    custom_price: Optional[str] = None,
) -> str:
    """
    Returns a formatted text ledger report.
    For structured data (API, JSON), use build_ledger_data() instead.
    """
    data = build_ledger_data(
        client=client,
        product=product,
        diluent_text=diluent_text,
        treatment_plan=treatment_plan,
        pricing_mode=pricing_mode,
        client_charge=client_charge,
        custom_price=custom_price,
    )
    return format_ledger(data)


# -----------------------------
# CLI entry point
# -----------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Create a Botox session ledger from treatment plan, dilution, and pricing inputs."
    )

    parser.add_argument("--client", required=True, help="Client name or identifier.")
    parser.add_argument("--product", default="Botox", help="Product name. Default: Botox.")
    parser.add_argument("--diluent", required=True, help="Diluent amount, such as '2.5 mL'.")
    parser.add_argument(
        "--treatment-plan",
        required=True,
        help=(
            "Treatment plan as lines like 'Forehead: 8 units'. "
            "Use quotes and separate lines with actual newlines or semicolons."
        ),
    )
    parser.add_argument(
        "--pricing-mode",
        default="standard",
        help="Pricing mode: standard, family-friend, or custom. Default: standard.",
    )
    parser.add_argument(
        "--client-charge",
        help="Actual client charge, such as '$420'. If omitted, recommended pricing is calculated.",
    )
    parser.add_argument(
        "--custom-price",
        help="Custom per-unit price for custom pricing mode, such as '$12/unit'.",
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format: text (default) or json.",
    )

    args = parser.parse_args()
    treatment_plan = args.treatment_plan.replace(";", "\n")

    try:
        if args.output_format == "json":
            data = build_ledger_data(
                client=args.client,
                product=args.product,
                diluent_text=args.diluent,
                treatment_plan=treatment_plan,
                pricing_mode=args.pricing_mode,
                client_charge=args.client_charge,
                custom_price=args.custom_price,
            )
            print(json.dumps(ledger_to_dict(data), indent=2))
        else:
            ledger = build_ledger(
                client=args.client,
                product=args.product,
                diluent_text=args.diluent,
                treatment_plan=treatment_plan,
                pricing_mode=args.pricing_mode,
                client_charge=args.client_charge,
                custom_price=args.custom_price,
            )
            print(ledger)

    except ValueError as error:
        print(f"Error: {error}")


if __name__ == "__main__":
    main()
