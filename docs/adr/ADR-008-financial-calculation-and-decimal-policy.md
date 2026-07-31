# ADR-008: Financial Calculation & Decimal Precision Policy

* **Decision ID**: `ADR-008`
* **Status**: `Proposed`
* **Context**: Financial calculations (ratios, growth rates, currency conversions, balance sheet reconciliations) across billions of currency units require exact arithmetic. Binary floating-point math (`float`/`double`) introduces IEEE 754 representation noise (e.g. `0.1 + 0.2 != 0.3`).
* **Decision**: Adopt a **Multi-Tier Decimal Precision Architecture**:
  1. **Source Preservation**: Preserved as raw unaltered string (e.g. `"2.850.000.000 Bin TL"`).
  2. **PostgreSQL Storage Precision**: `NUMERIC(28, 6)` (`Proposed`) in PostgreSQL `financial_facts` table.
  3. **Python Decimal Working Context Precision**: In-memory evaluation in Python sets working context precision (e.g. `decimal.getcontext().prec = 38` significant digits) to prevent intermediate truncation errors.
  4. **Metric-Specific Quantization Exponent**: Result scale formatting uses Python's `Decimal.quantize()` with metric-specific exponents:
     * **Percentages & Ratios**: `quantize(Decimal('0.0001'))` (supporting 0.0001% / 4 decimal place ratio precision).
     * **FX Rates**: `quantize(Decimal('0.00000001'))` (supporting up to 8 decimal place exchange rate precision).
     * **Currency Values**: `quantize(Decimal('0.01'))` or scale-adjusted integer quantization for rounded reporting units.
  5. **Rounding Modes & Overflow Control**: Governed by formula registry contracts (e.g. `ROUND_HALF_UP`). Arithmetic exceptions (`decimal.Overflow`, `decimal.Underflow`, `decimal.DivisionByZero`) raise explicit domain errors.
  6. **DTO Serialization Format**: Financial values are serialized as `str` in JSON DTO payloads to prevent float coercion during API transfers.
  7. **Metric-Specific UI Presentation Formatting**: Presentation formatting is linked to metric definition type (currency, percentage, ratio, FX rate, count) rather than imposing a single global 2-decimal rule across all UI elements.
  * **Prohibition Scope**: Standard binary `float` or `double` data types are **STRICTLY PROHIBITED** within financial domain calculation modules and fact stores. Non-financial measurements, UI animation coordinates, layout bounds, and graphic rendering coordinates (e.g. Flutter canvas rendering points) are **EXPLICITLY OUT OF SCOPE** for this prohibition.
* **Risk Reduction & Limitations**: Decimal arithmetic eliminates binary floating-point representation artifacts (IEEE 754 noise). However, Decimal DOES NOT prevent wrong mathematical formulas, incorrect unit scale multipliers, or premature rounding errors. Precision rules must be governed by formula registry contracts.
* **Alternatives Considered**:
  1. *IEEE 754 Floating-Point (`float`)*: Unacceptable rounding errors and reconciliation failures.
  2. *Single Global Decimal Scale*: Cannot represent high-precision FX rates or fractional interest rate percentages cleanly without truncating working calculations.
* **Security Impact**: Prevents financial manipulation caused by floating-point truncation bugs.
* **Data Integrity Impact**: Enforces exact base-10 mathematical evaluation across core metrics.
* **MVP Impact**: Established pure Python domain module in `packages/financial-domain`.
* **Cost Impact**: Negligible CPU impact for financial formula workloads.
* **Scalability Impact**: Pure functions are parallelizable across worker containers.
* **Risks**: Developer inadvertently casting `Decimal` to `float` during JSON serialization (mitigated by custom Pydantic serializer).
* **Revisit Trigger**: Requirement for high-frequency quantitative simulation requiring SIMD C++ floating-point acceleration.
