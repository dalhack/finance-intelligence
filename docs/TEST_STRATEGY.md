# Finance Intelligence — Quality Assurance & Test Strategy

> **Document ID**: `TST-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. Test Pyramid & Automation Architecture

```
                  /\
                 /  \  E2E / Mobile UI Tests (Flutter Integration - Proposed)
                /----\
               /      \  LLM Evaluation & Prompt Injection Benchmarks
              /--------\
             /          \  Contract & API Integration Tests (FastAPI / Schemathesis)
            /------------\
           /              \  PostgreSQL Row-Level Security (RLS app.current_organization_id) Isolation Tests
          /----------------\
         /                  \  Property-Based Financial Calculation Tests (Hypothesis)
        /--------------------\
       /                      \  Unit Tests (PyTest / Dart Test - Target 85%+ Coverage)
      /------------------------\
```

---

## 2. Specialized Test Methodologies

### 2.1 Property-Based Financial Calculation Testing
* **Framework**: Python `hypothesis` library.
* **Objective**: Generate synthetic `decimal.Decimal` financial numbers (using working context precision `prec = 38`) to verify ratio calculation stability, division-by-zero handling, and rounding precision.
* **Assertion Rules**: Ratios MUST NEVER raise unhandled system exceptions; output MUST ALWAYS yield a valid `CalculationResult` or explicit domain exception (`ZeroDivisionError`, `decimal.Overflow`, `CALCULATION_OVERFLOW_EXCEEDED`).

### 2.2 Golden Dataset Benchmark Suite
* **Document Extraction Golden Dataset**: 50 real-world banking financial filings (PDF/XLSX) manually annotated with exact cell coordinates and values. Automated candidate parsers are evaluated against this suite; confidence scoring routes extractions < 0.85 to human review.
* **Calculation Golden Dataset**: 100 historical bank comparison scenarios pre-computed in gold Excel models. Calculation Engine outputs MUST match gold Excel values.

### 2.3 LLM Faithfulness & Prompt Injection Benchmarks
* **Citation Verification Test**: Automated evaluator checks test queries. Every numerical assertion in LLM output text is cross-referenced against the deterministic fact store. Target citation verification score is ≥ 99.0%.
* **Indirect Prompt Injection Benchmark (`SEC-BENCH-01`)**: Suite of 50 adversarial PDFs containing hidden injection instructions. **PASS CRITERIA**: 0 successful jailbreaks; zero secret leaks; 100% structured tool execution compliance.

### 2.4 Multi-Tenant Row-Level Security (RLS) Isolation Testing
* **Cross-Tenant RLS Integration Test**: Automated test harness executes parallel API requests using Auth credentials of Organization A attempting to query database rows or documents belonging to Organization B.
* **PASS CRITERIA**: 100% of unauthorized requests return zero rows or HTTP 403/404 with zero cross-tenant leakage.

---

## 3. Automated CI/CD Release Gates

| Quality Gate | Trigger Condition | Pass Threshold | Blocking Action |
|---|---|---|---|
| **Unit & Property Tests** | Every Git Push | 100% Pass Rate (>= 85% Code Coverage) | Block Merge |
| **API Contract Validation** | Pull Request to `main` | Schemathesis zero contract drift errors | Block Merge |
| **Calculation Gold Suite** | Pull Request to `main` | 100.0% Exact Match against Gold Excel Models | Block Merge |
| **RLS Negative Security Suite** | Pull Request to `main` | 0 Cross-Tenant Data Leaks across all DB tables | Block Merge |
| **Prompt Injection Suite** | Nightly Build | 0 Jailbreaks across 50 adversarial payloads | Block Deployment |
| **Load & Latency Gate** | Pre-Release Staging | P95 API Latency < 300 ms @ 100 RPS | Block Production Release |
