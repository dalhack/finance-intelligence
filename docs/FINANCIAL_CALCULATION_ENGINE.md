# Finance Intelligence — Financial Calculation Engine & Precision Specifications

> **Document ID**: `CAL-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. Engine Core & Multi-Tier Precision Policy

The **Calculation Engine** is a deterministic, isolated pure Python domain module. It eliminates binary floating-point representation errors (IEEE 754 artifacts) by using arbitrary-precision `decimal.Decimal` math.

> [!IMPORTANT]
> **Decimal Scope & Limitations**: Decimal arithmetic prevents binary representation errors (e.g. `0.1 + 0.2 != 0.3`). However, Decimal DOES NOT automatically prevent incorrect formula logic, improper unit scaling, or premature rounding errors. Precision and rounding rules must be strictly enforced at designated pipeline stages.

### Multi-Tier Precision Definitions

| Precision Tier | Data Type / Implementation | Target Scale / Exponent | Execution Stage & Description |
|---|---|---|---|
| **1. Source Precision** | `str` (Raw Unaltered Text) | Original String | Preserved exactly as reported in source filings (e.g. `"2.850.000.000 Bin TL"`). |
| **2. Storage Precision** | `NUMERIC(28, 6)` (`Proposed`) | 28 digits, 6 decimals | Database persistence in PostgreSQL `financial_facts` table. |
| **3. Working Calculation** | `decimal.Decimal` | `decimal.getcontext().prec = 38` | In-memory evaluation during formula execution in Python. |
| **4. Ratio / Percentage** | `decimal.Decimal` | `quantize(Decimal('0.0001'))` | Preserves fractional percentage precision (supporting 0.0001% granularity). |
| **5. FX Rate Precision** | `decimal.Decimal` | `quantize(Decimal('0.00000001'))` | Exchange rate conversions (supporting 8 decimal places). |
| **6. Display Precision** | Formatted `str` | Metric-Specific Formatting | UI presentation boundary linked to metric definition type (currency, %, ratio, FX rate, count). |

### Rounding Rules & Stage Enforcement
* **Rounding Rules**: Governed by metric and formula definition versioning rules (e.g. `ROUND_HALF_UP` applied at metric boundary output stage).
* **Rounding Stage**: Rounding MUST occur ONLY at the final presentation/output boundary. Intermediate steps during multi-stage ratio calculations MUST preserve full `prec = 38` working context precision.
* **Overflow Handling**: Exceeding maximum precision bounds raises an explicit domain exception (`decimal.Overflow` or `CALCULATION_OVERFLOW_EXCEEDED`).

---

## 2. Core Python Calculation Contract & Ratio Lineage

```python
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Dict, Any, NamedTuple, Optional
from uuid import UUID

# Configure working context precision to 38 significant digits
getcontext().prec = 38


class CalculationResult(NamedTuple):
    value: Decimal
    unit: str
    formula_code: str
    formula_version: int
    numerator_fact_id: Optional[UUID]
    denominator_fact_id: Optional[UUID]
    input_lineage: Dict[str, Any]


def compute_ratio(
    numerator: Decimal,
    denominator: Decimal,
    formula_code: str,
    numerator_fact_id: Optional[UUID] = None,
    denominator_fact_id: Optional[UUID] = None,
    version: int = 1,
) -> CalculationResult:
    if denominator == Decimal("0"):
        raise ZeroDivisionError(f"Formula {formula_code} failed: Denominator is zero.")

    # Working precision evaluation with prec = 38
    raw_ratio = (numerator / denominator) * Decimal("100")
    # Final output quantization to 4 decimal places for ratio percentage
    rounded_value = raw_ratio.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    return CalculationResult(
        value=rounded_value,
        unit="%",
        formula_code=formula_code,
        formula_version=version,
        numerator_fact_id=numerator_fact_id,
        denominator_fact_id=denominator_fact_id,
        input_lineage={"numerator": str(numerator), "denominator": str(denominator)},
    )
```

---

## 3. Stock vs. Flow Period Semantics

* **Stock Metrics** (Point-in-Time, e.g., `total_assets`, `total_loans`, `total_deposits`, `total_equity`): Measured at exact period end date (e.g. 31.12.2025). Cannot be summed across quarters.
* **Flow Metrics** (Cumulative / Period Duration, e.g., `net_income`): Measured over a time interval (e.g., 12 months or 3 months). Annualization rules apply when comparing Q1 (3 months) against Full Year (12 months).

---

## 4. 11 Core MVP Financial Metric Definitions

*(Detailed specifications for `total_assets`, `total_loans`, `total_deposits`, `total_equity`, `net_income`, `non_performing_loans`, `capital_adequacy_ratio`, `return_on_assets`, `return_on_equity`, `net_interest_margin`, `loan_to_deposit_ratio` are defined with required inputs, formulas, ratio lineage constraints, and validation ranges.)*

---

## 5. Property-Based Testing

```python
from hypothesis import given, strategies as st
from decimal import Decimal, getcontext

getcontext().prec = 38


@given(
    st.decimals(min_value=Decimal("100.00"), max_value=Decimal("1000000000000.00"), places=2),
    st.decimals(min_value=Decimal("100.00"), max_value=Decimal("1000000000000.00"), places=2),
)
def test_ratio_calculation_properties(loans, deposits):
    result = compute_ratio(loans, deposits, "loan_to_deposit_ratio")
    assert result.value >= Decimal("0.0000")
    assert isinstance(result.value, Decimal)
```
