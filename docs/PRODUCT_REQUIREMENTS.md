# Finance Intelligence — Product Requirements Document (PRD)

> **Document ID**: `PRD-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Target Baseline**: `MVP 1.0 (Proposed Baseline)`  
> **Classification**: `INTERNAL`

---

## 1. Product Vision & Core Objective

**Finance Intelligence** is an enterprise financial analysis, comparison, and reporting platform. It enables decision-makers, financial analysts, and corporate executives to query complex financial datasets, multi-bank performance metrics, official regulatory filings, and corporate documents through a natural language interface.

Unlike generic conversational LLM tools, **Finance Intelligence** incorporates:
1. **Deterministic Calculation Controls**: Financial ratios and metrics are calculated by a pure calculation engine operating on Python `decimal.Decimal` arbitrary-precision math (using working context precision `prec = 38` and metric-specific quantization).
2. **Evidence Lineage**: Extracted financial facts and claims map to source document, version, page, table, row, and cell coordinates.
3. **Multi-Tier Security & Policy Enforcement**: User authorization, defense-in-depth tenant isolation (PostgreSQL RLS `app.current_organization_id`), data classification (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `STRICTLY_CONFIDENTIAL`, `PERSONAL_DATA`), and external AI exposure rules are evaluated prior to retrieval, prompt construction, and export.
4. **Canonical Visualization**: Tables and dynamic charts (Bar, Line, Stacked Bar, Pie) are rendered natively on the client from a validated, type-safe schema (`ChartSpec`) tied to a single canonical result dataset ID (`result_dataset_id`).

---

## 2. Target Personas & Primary Use Cases

### Personas
* **Financial Analyst**: Compares bank financial statements, liquidity ratios, and capital adequacy metrics across multiple quarters.
* **Corporate Executive**: Requires executive summaries, key driver insights, budget variance analysis, and export to XLSX/PDF.
* **Compliance Auditor**: Verifies disclosures and traces evidence to primary source filings.

### Primary Use Cases & Prompt Examples
1. **Multi-Bank Peer Comparison**: *"Türkiye’de aktif büyüklüğüne göre ilk iki bankayı son ortak çeyrek itibarıyla karşılaştır."*
2. **Financial Trend Visualization**: *"Banka A ile Banka B’nin toplam aktiflerini son sekiz çeyrek için çubuk ve çizgi grafikle göster."*
3. **Derived Ranking & Growth Analysis**: *"Kredi büyümesi en yüksek bankaları sırala."*
4. **Ratio Reconciliation & Analytical Interpretation**: *"Bu iki bankanın sermaye yeterlilik oranlarını karşılaştır ve farklılığın olası nedenlerini yorumla."*
5. **Document Variance Analysis**: *"Yüklediğim finansal rapora göre bütçe sapmalarını tablo halinde göster."*
6. **Regulatory Reference Query**: *"İlgili mevzuat hükümlerini resmî kaynaklarıyla açıkla."*
7. **Comprehensive Audit Executive Report**: *"Sonucu yönetici özeti, tablo, grafik ve kaynakça halinde oluştur."*

---

## 3. Requirement Catalog (43 Unique Requirement IDs)

### 3.1 Functional Requirements (`FR-*`)

* **`FR-001`**: The system MUST allow users to enter free-form financial and regulatory queries up to 4,000 characters.
* **`FR-002`**: The system MUST parse, extract, and index financial tables and structured data from user-uploaded PDF, XLSX, and CSV files.
* **`FR-003`**: The system MUST support document deduplication via server-computed SHA-256 hashing and track version history for re-uploaded files.
* **`FR-004`**: The system MUST extract, normalize, and store 11 MVP canonical financial metrics into PostgreSQL (`FinancialFact` entity).
* **`FR-005`**: The system MUST perform peer comparisons across 2 or more institutions over aligned reporting periods.
* **`FR-006`**: The system MUST compute derived metrics strictly within the deterministic Calculation Engine using Python Decimal math.
* **`FR-007`**: The system MUST generate canonical `TableSpec` and `ChartSpec` JSON contracts tied to a single `result_dataset_id` for client-side visualization.
* **`FR-008`**: The system MUST link every extracted value to an `Evidence` record specifying document ID, version, page, table, row, and cell coordinate.
* **`FR-009`**: The system MUST provide an interactive evidence drill-down drawer in the mobile UI to display source snippets and highlight original tabular cells.
* **`FR-010`**: The system MUST allow exporting canonical analysis results to CSV, XLSX, and client-rendered PNG chart images.
* **`FR-011`**: The system MUST support a Regulatory Module adapter interface. In MVP, calls return an explicit `REGULATORY_DATA_UNAVAILABLE` or `NOT_IMPLEMENTED` code without returning sample text as real legislation.
* **`FR-012`**: The system MUST maintain append-only audit logging (`AuditEvent`) for user actions, document uploads, tool executions, policy decisions, and quality gate results.

### 3.2 Non-Functional Requirements (`NFR-*`)

* **`NFR-001` Latency**: Synchronous API endpoints SHOULD respond within 300 ms (p95). Asynchronous analysis jobs MUST render first progress within 2 seconds via Server-Sent Events (SSE).
* **`NFR-002` Scalability**: Backend services MUST support horizontal auto-scaling on Cloud Run from 0 to 50 container instances.
* **`NFR-003` Availability**: Backend infrastructure target monthly service uptime is 99.9% excluding scheduled maintenance.
* **`NFR-004` Calculation Precision**: Financial calculations MUST prevent binary floating-point representation errors by using Python Decimal data types.
* **`NFR-005` Client Responsiveness**: Client app MUST maintain fluid UI transitions on supported mobile devices, supporting offline viewing of cached historical reports.
* **`NFR-006` File Size Limit**: System MUST support document uploads up to 50 MB per file, executing async processing for files exceeding 5 MB.

### 3.3 Security Requirements (`SEC-*`)

* **`SEC-001`**: API calls from mobile clients MUST enforce Firebase Authentication ID Token verification and Firebase App Check attestation.
* **`SEC-002`**: No secret keys (API keys, service account credentials, database tokens) shall exist within client binary builds.
* **`SEC-003`**: File uploads MUST route via short-lived (15-minute expiration) GCS Signed URLs generated after object-level authorization checks.
* **`SEC-004`**: Uploaded files MUST undergo magic byte MIME validation, server-side SHA-256 hashing, and malware scanning prior to ingestion.
* **`SEC-005`**: Multi-tenant data isolation MUST be enforced via defense-in-depth layers, including PostgreSQL Row-Level Security (RLS using `app.current_organization_id`) and GCS path isolation (`/tenants/{org_id}/...`).
* **`SEC-006`**: Web retrieval tool calls MUST enforce a domain allowlist, prevent SSRF, block private IP ranges (RFC 1918), and limit redirect loops (max 3).
* **`SEC-007`**: Prompts sent to external LLM providers MUST undergo indirect prompt injection filtering and XML tag context isolation.
* **`SEC-008`**: LLM tool JSON schemas MUST NOT accept tenant context (`organization_id`, `tenant_id`, `user_id`) from LLM inputs; all tenant context MUST be server-injected via `ExecutionContext`.
* **`SEC-009`**: Application logs MUST pseudonymize tenant and user identifiers (`user_hash`, `org_hash`) and redact PII fields prior to writing to central log sinks.

### 3.4 Data Requirements (`DATA-*`)

* **`DATA-001`**: Data entities MUST be assigned a data classification: `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `STRICTLY_CONFIDENTIAL`, or `PERSONAL_DATA`.
* **`DATA-002`**: Financial values MUST store raw original string values (`value`, `currency`, `unit`, `scale`) without alteration, alongside normalized values (`normalized_value`, `normalized_currency`).
* **`DATA-003`**: Financial calculations MUST prohibit implicit currency conversion without explicit exchange rate tracking (rate, rate_date, rate_source).
* **`DATA-004`**: Audit events MUST be append-only with cryptographic hash chaining to provide tamper-evident logs.
* **`DATA-005`**: Data retention policies MUST support hard deletion of tenant documents upon request while preserving anonymized audit trails under legal hold rules.

### 3.5 AI / LLM Requirements (`AI-*`)

* **`AI-001`**: LLMs MUST be isolated behind a capability-matrix Model Provider Abstraction layer supporting Anthropic Claude (Direct API or GCP Vertex AI).
* **`AI-002`**: Model provider calls MUST use Bounded Tool Schemas with strict JSON Schema output validation. Tool schemas MUST NOT accept `organization_id` or `tenant_id` from the model; tenant context is injected server-side.
* **`AI-003`**: LLMs MUST NOT perform direct arithmetic calculation; all numbers in text responses MUST be validated against the deterministic calculation output.
* **`AI-004`**: LLM prompts MUST incorporate system instructions enforcing zero speculative claims and mandating inline citation tags (`[EIV-XXXX]`).
* **`AI-005`**: LLM token consumption SHOULD implement prompt caching for static system prompts to optimize latency and token expenditure.

### 3.6 Mobile UX Requirements (`UX-*`)

* **`UX-001`**: Proposed mobile client baseline target is Flutter 3.x with Riverpod 2.x state management following Clean Architecture patterns.
* **`UX-002`**: Query screen MUST feature a prompt input area, file attachment chip, institution filter chips, and period selection controls.
* **`UX-003`**: Analysis execution MUST display real-time progress status updates (`queued` ➔ `extracting` ➔ `calculating` ➔ `validating` ➔ `completed` / `completed_with_warnings`).
* **`UX-004`**: Analysis results MUST format into tabbed sections: Executive Summary, Structured Tables, Interactive Dynamic Charts, Regulatory Findings, and Sources/Evidence.
* **`UX-005`**: Tapping a cited number or chart element SHOULD open the Evidence Drill-Down Drawer, presenting source page preview and table cell coordinates.
* **`UX-006`**: Screen components SHOULD support WCAG 2.1 AA accessibility standards, high-contrast mode, and dynamic font scaling.

---

## 4. MVP Scope vs. Deferred Scope

| Feature Category | Proposed MVP Scope (Phase 1-5 Baseline) | Deferred Scope (Phase 6+) |
|---|---|---|
| **Authentication** | Firebase Auth (Email/Pass, Google Sign-in) + App Check | Enterprise SAML SSO / Okta Integration |
| **Supported Files** | PDF, XLSX, CSV (Max 50MB) | DOCX, PPTX, EML, Scanned Documents |
| **Metrics** | 11 Core MVP Financial Metrics | Custom User-Defined Dynamic Metric Formulas |
| **Calculations** | Historical Peer Comparison, Ratios, Variance | Monte Carlo Forecasting, DCF Engine |
| **Web Retrieval** | Feature-flagged allowlisted web search for official sources | Unrestricted web search crawler |
| **Regulation** | Placeholder adapter returning explicit `REGULATORY_DATA_UNAVAILABLE` | Automated regulatory parser pipeline |
| **Export Formats** | CSV, XLSX (data + formulas), PNG (charts) | Automated custom PPTX deck generation |
| **Multi-Tenancy** | Shared PostgreSQL database with Row-Level Security (RLS) | Schema-per-tenant or Database-per-tenant isolation |

---

## 5. Success Metrics & Quality Criteria

1. **Calculation Precision**: 100.0% match against gold-standard Excel financial models across all 11 metrics.
2. **Citation Faithfulness Score**: Target ≥ 99.0% of numerical assertions in summaries mapping directly to valid `Evidence` records.
3. **Prompt Injection Resilience**: 0 successful jailbreak attacks against golden prompt injection test benchmarks (`SEC-BENCH-01`).
4. **App Store Stability Target**: Zero fatal crashes attributed to data parsing or chart rendering (`Crashlytics free rate > 99.9%`).
