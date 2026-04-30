---
name: botox-session-ledger
description: Creates an operational Botox session ledger from a user-provided client, treatment plan, and dilution details. Parses treatment areas and units, validates structure, calculates concentration, per-area injection volumes, U-100 syringe markings, vial reconciliation, consumable costs, product cost used, recommended client pricing, and gross margin estimates. Supports standard pricing, family-friend pricing, and custom per-unit pricing. Does not recommend Botox doses, treatment plans, injection sites, routes, frequency, or patient-specific treatment decisions.
---

# Botox Session Ledger

This skill converts a user-provided Botox treatment plan into a structured operational ledger for:

- inventory reconciliation
- consumable cost tracking
- profitability analysis
- pricing recommendations
- treatment-session auditing

The model handles orchestration and clarification.

All deterministic parsing, validation, calculations, and formatting are performed by:

`scripts/botox_session_ledger.py`

Default Botox pricing, consumables, operational assumptions, and treatment references are stored in:

`references/botox_cost_assumptions.md`

---

# When to use this skill

Use this skill when the user wants to:

- Create a Botox treatment ledger
- Calculate concentration from dilution
- Convert Botox units into injection volume
- Convert injection volume into U-100 syringe markings
- Track remaining vial inventory
- Estimate product cost used
- Estimate session consumable cost
- Recommend client pricing
- Calculate gross margin
- Audit whether a session exceeds vial inventory

Examples:

- "Create a Botox ledger for Jane."
- "What would I make on this Botox treatment?"
- "How many units remain in the vial?"
- "What should I charge a family friend for this treatment?"

---

# When NOT to use this skill

Do NOT use this skill for:

- Botox dose recommendations
- Clinical treatment planning
- Injection-site recommendations
- Route recommendations
- Frequency recommendations
- Patient-specific medical decisions

Examples:

- "How many units should I inject in the masseters?"
- "What dose should I use for forehead lines?"

Politely decline and request user-selected treatment units instead.

---

# Expected inputs

## Required

- Client name
- Product name
- Diluent amount in mL
- Treatment plan:
  - area
  - planned units

Example:

```text
Client: Jane
Product: Botox
Diluent: 2.5 mL

Treatment plan:
Forehead Lines: 8 units
Frown Lines: 12 units
Masseters: 20 units each side
```

---

## Optional

- Client charge
- Pricing mode
- Custom per-unit pricing

### Supported pricing modes

## Standard

Uses:

```text
20% target gross margin
```

## Family-friend

Uses:

```text
$10.00/unit
```

## Custom

User provides:

```text
$12/unit
```

If omitted, use:

```text
Standard
```

---

# Step-by-step instructions

## 1. Parse inputs

Extract:

- client
- product
- diluent amount
- treatment areas
- treatment units
- optional pricing inputs

If required values are missing, ambiguous, or unitless, ask for clarification.

Do not guess.

---

## 2. Validate inputs

Confirm:

- treatment units are numeric
- treatment units are positive
- Botox treatment plans use **units**
- diluent is provided in **mL**

Reject invalid entries.

Examples:

Reject:

```text
Forehead: eight units
Forehead: -8 units
Forehead: 8 mg
Diluent: normal dilution
```

---

## 3. Calculate concentration

Assume:

```text
100-unit Botox vial
```

Calculate:

```text
concentration = 100 ÷ diluent
```

Example:

```text
100 ÷ 2.5 = 40 units/mL
```

---

## 4. Calculate area-level volumes

For each treatment area:

```text
volume = area units ÷ concentration
```

Example:

```text
8 ÷ 40 = 0.20 mL
```

Also calculate:

- U-100 syringe markings

Important:

```text
1 mL = 1 cc
1 mL = 100 U-100 syringe markings
```

Example:

```text
0.30 mL = 0.30 cc = 30 U-100 markings
```

U-100 syringe markings are scale references and are **not** used to estimate syringe count.

---

## 5. Calculate treatment summary

Calculate:

- total planned dose
- total volume
- total U-100 syringe markings
- expected vial remaining
- percent of vial used

If planned units exceed 100:

Generate warning.

---

## 6. Calculate financial summary

Using default assumptions from references:

Calculate:

- product cost used
- saline allocation
- syringe cost
- glove cost
- prep pad cost
- total consumables
- total session cost

Syringe usage is estimated operationally as:

```text
1 syringe per 1–2 treatment areas
3–4 areas = 2 syringes
5–6 areas = 3 syringes
```

This avoids incorrectly treating U-100 syringe markings as Botox units.

---

## 7. Calculate pricing

If client charge is provided:

Calculate:

- gross margin
- gross margin %

If client charge is NOT provided:

Calculate recommended charge using pricing mode.

### Standard

Use:

```text
20% target gross margin
```

Formula:

```text
session cost ÷ (1 − margin)
```

### Family-friend

Use:

```text
$10.00 per unit
```

### Custom

Use:

```text
$X per unit
```

---

## 8. Generate session ledger

Use:

`scripts/botox_session_ledger.py`

Return the ledger below.

---

# Expected output format

Return:

```text
Botox Session Ledger

Client: [name]
Product: Botox
Concentration: [value] units/mL

Treatment Plan

| Area | Units | Arithmetic | Volume | U-100 |
|---|---:|---|---:|---:|

Treatment summary:

Total planned dose: [value] units

Total volume: [value] mL

Total U-100 syringe markings: [value]

Expected vial remaining: [value] units

Vial used: [value]%

Financial summary:

Product cost used: $[value]

Saline allocation: $[value]

Syringes required: [value]

Syringe cost: $[value]

Prep pads estimated: [value]

Glove cost: $[value]

Consumables: $[value]

Total session cost: $[value]

Pricing summary:

Pricing mode: [value]

If actual charge provided:

Client charge: $[value]

If recommended pricing:

Recommended charge: $[value]

Recommended per-unit price: $[value]

Gross margin: $[value]

Gross margin %: [value]

Flags:

- Dose values were user-provided.
- This skill does not validate clinical appropriateness.
- Pricing estimates do not represent final profitability.
- Pricing does not include malpractice insurance, provider compensation, rent, taxes, merchant fees, payroll, marketing, licensing, spoilage, or other fixed operating expenses.
- Additional warnings if applicable.
```

---

# Important limitations

Always refuse:

- Botox dose recommendations
- Injection-site recommendations
- Clinical treatment planning
- Patient-specific medical decisions

Example:

User:

```text
How much Botox should I inject in the masseters?
```

Response:

```text
This skill does not recommend Botox doses, treatment areas, routes, or clinical treatment plans.

Provide your intended treatment units, and I can generate an operational session ledger.
```