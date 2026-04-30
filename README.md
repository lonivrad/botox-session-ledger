# Botox Session Ledger

Video Demo:  
https://youtu.be/2hc-wjDLE2Q

---

# Overview

This project implements a reusable AI skill called:

`botox-session-ledger`

The skill converts a user-provided Botox treatment plan into an operational session ledger.

It combines:

- AI workflow orchestration
- deterministic Python calculations
- structured validation
- inventory reconciliation
- pricing recommendations
- profitability analysis

This is not a clinical dosing tool.

The user must provide their own intended treatment units.

The skill explicitly refuses:

- dose recommendations
- treatment planning
- injection-site recommendations
- route recommendations
- frequency recommendations
- patient-specific clinical decisions

---

# Why I Built This

I currently work in healthcare and also perform aesthetic injectable treatments.

In real-world practice, small math mistakes, unit confusion, and incomplete cost visibility can directly impact:

- inventory tracking
- profitability
- pricing consistency
- operational efficiency

I wanted to build a reusable operational skill that solves an actual workflow I encounter in day-to-day practice.

Rather than acting as a simple calculator, this skill acts as a mini practice-operations agent.

---

# What The Skill Does

The skill takes:

- client name
- product
- diluent amount
- treatment areas
- planned treatment units

Optional:

- actual client charge
- pricing mode
- custom per-unit pricing

The Python script then:

## Parses and validates input

- confirms treatment units are numeric
- confirms positive values
- rejects invalid units such as mg or mcg
- rejects ambiguous dilution values

## Calculates dilution

Formula:

```text
100 units ÷ diluent amount (mL)
```

Example:

```text
100 ÷ 2.5 = 40 units/mL
```

## Calculates treatment volumes

Formula:

```text
units ÷ concentration
```

Example:

```text
8 ÷ 40 = 0.20 mL
```

Also converts:

```text
1 mL = 1 cc
1 mL = 100 U-100 syringe markings
```

## Performs inventory reconciliation

Calculates:

- total planned dose
- total volume
- total U-100 markings
- expected vial remaining
- percent of vial used

## Calculates operational costs

Uses default assumptions:

- Botox vial = $656
- Saline = $5.20
- Syringe package = $18 / 100 syringes
- Gloves = $0.010 each
- Alcohol prep pads = $0.002 each

Calculates:

- product cost used
- saline allocation
- syringe cost
- glove cost
- prep pad cost
- total consumables
- total session cost

## Calculates pricing

Supports:

### Standard pricing

20% target gross margin

### Family-friend pricing

$10/unit

### Custom pricing

User-provided $X/unit

Calculates:

- recommended charge
- recommended per-unit price
- gross profit
- gross margin %

---

# Project Structure

```text
hw5-Loni/
├─ agents/
│  └─ skills/
│     └─ botox-session-ledger/
│        ├─ SKILL.md
│        ├─ scripts/
│        │  └─ botox_session_ledger.py
│        └─ references/
│           └─ botox_cost_assumptions.md
├─ README.md
```

---

# How To Run

From the repository root:

```bash
cd ~/code/hw5-Loni
```

Run with Python:

```bash
python3 agents/skills/botox-session-ledger/scripts/botox_session_ledger.py \
  --client "Jane" \
  --product "Botox" \
  --diluent "2.5 mL" \
  --treatment-plan "Forehead Lines: 8 units; Frown Lines: 12 units; Masseters: 20 units each side" \
  --client-charge "$420"
```

---

# Test Cases

## Test 1 — Normal case

Client:

Jane

Dilution:

2.5 mL

Treatment:

- Forehead: 8 units
- Frown Lines: 12 units
- Masseters: 20 units each side

Client charge:

$420

Output:

- 60 total units
- 1.50 mL total volume
- 40 units remaining
- 5.5% gross margin

---

## Test 2 — Family-friend pricing

Client:

Sarah

Pricing mode:

Family-friend

Output:

- 32 total units
- Recommended charge = $320
- Gross margin = 33.8%

---

## Test 3 — Safety refusal

Input:

```text
How many units should I inject into the masseters?
```

Output:

Skill refuses clinical dosing recommendations.

---

## Test 4 — Different reconstitution

Client:

Emily

Dilution:

1.0 mL

Output:

- Concentration changes to 100 units/mL
- Volume calculations change
- U-100 markings change
- Pricing updates dynamically

---

# Most Important Technical Fix

During testing I found a conceptual bug.

Original syringe logic incorrectly estimated syringe count using:

```text
total U-100 markings ÷ 30
```

This could incorrectly treat U-100 markings as Botox units.

I fixed this by changing syringe estimation to:

```text
1 syringe per 1–2 treatment areas
```

Implementation:

```python
math.ceil(treatment_area_count / 2)
```

This made:

Jane:

3 treatment areas

Old:

5 syringes

New:

2 syringes

This slightly improved margin calculations while making the operational logic conceptually correct.

---

# What Worked Well

- Strong alignment between SKILL.md, references, and Python script
- Real-world workflow applicability
- Dynamic pricing logic
- Safety boundaries
- Refusal handling
- Agent successfully discovered and executed the skill

---

# Limitations

This skill does not include:

- malpractice insurance
- provider compensation
- payroll
- rent
- taxes
- merchant processing fees
- licensing
- marketing
- spoilage
- financing costs
- software subscriptions
- fixed operating expenses

This skill also does not make clinical decisions.

It only performs operational and financial calculations using user-provided treatment values.
