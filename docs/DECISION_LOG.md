# Finance Intelligence — Architecture Decision Log & Assumptions Master

> **Document ID**: `DEC-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. Master Assumption Catalog (Unique IDs)

* **`ASM-001`**: Proposed mobile application target is cross-platform iOS and Android using Flutter 3.x with Riverpod 2.x state management. (`Status: Proposed`)
* **`ASM-002`**: Firebase Authentication and Firebase App Check provide edge identity and device integrity verification for MVP. (`Status: Proposed`)
* **`ASM-003`**: Backend control plane will run on Google Cloud Run utilizing Python 3.12, FastAPI, and Pydantic v2. (`Status: Proposed`)
* **`ASM-004`**: Cloud SQL PostgreSQL 16 with `pgvector` extension will serve as canonical source-of-truth for financial facts and vector embeddings, enforcing Row-Level Security (RLS using `app.current_organization_id`). (`Status: Proposed`)
* **`ASM-005`**: Cloud Firestore will handle transient real-time chat state sync and live job progress indicators for mobile clients. (`Status: Proposed`)
* **`ASM-006`**: All financial calculation arithmetic must use multi-tier Decimal arbitrary-precision numbers with rounding rules at metric boundary outputs. (`Status: Proposed`)
* **`ASM-007`**: Documents uploaded by users default to `CONFIDENTIAL` data classification. (`Status: Proposed`)
* **`ASM-008`**: External LLMs (Anthropic Claude via direct API or GCP Vertex AI) will be isolated behind a capability-matrix provider adapter. (`Status: Proposed`)
* **`ASM-009`**: LLMs are prohibited from performing direct math calculations or drawing pixels/charts. (`Status: Proposed`)
* **`ASM-010`**: Charts are rendered dynamically on the Flutter client using a type-safe `ChartSpec` JSON contract bound to a `result_dataset_id`. (`Status: Proposed`)
* **`ASM-011`**: Web retrieval (`search_public_sources`) is feature-flagged and restricted strictly to an allowlist of official financial/regulatory domains. (`Status: Proposed`)
* **`ASM-012`**: Document uploads execute via 15-minute pre-signed GCS PUT URLs with server-computed SHA-256 hash calculation upon completion. (`Status: Proposed`)
* **`ASM-013`**: OCR is used strictly as an async fallback when text density is < 50 chars/page or unparseable font encodings exist. (`Status: Proposed`)
* **`ASM-014`**: Multi-tenant data isolation is enforced via defense-in-depth layers, including PostgreSQL Row-Level Security (RLS using `app.current_organization_id`). (`Status: Proposed`)
* **`ASM-015`**: Regulatory text ingestion pipeline is stubbed via a placeholder adapter for MVP returning explicit `REGULATORY_DATA_UNAVAILABLE` errors. (`Status: Proposed`)
* **`ASM-016`**: PDF, XLSX, and CSV are primary MVP file ingestion formats; DOCX support is deferred to Phase 6. (`Status: Deferred`)
* **`ASM-017`**: Audit trail logs are append-only with cryptographic hash chaining to provide tamper-evident records using pseudonymized IDs (`user_hash`, `org_hash`). (`Status: Proposed`)
* **`ASM-018`**: Cost controls enforce per-user daily token caps and per-organization monthly spending limits. (`Status: Proposed`)
* **`ASM-019`**: Quality gates separate informational `completed_with_warnings` states from blocking `FAILED` states. (`Status: Proposed`)
* **`ASM-020`**: Proposed cloud deployment region is `europe-west1` (Belgium), subject to legal and compliance signoff on KVKK/GDPR data locality. (`Status: Proposed`)

---

## 2. Summary of 10 Core Architectural Decisions & ADR References

| Decision ID | ADR Reference | Subject / Choice | Status | Rationale Summary |
|---|---|---|---|---|
| **`DEC-001`** | [ADR-001](adr/ADR-001-mobile-technology-stack.md) | Mobile Stack: Flutter + Riverpod | `Proposed` | Native high-performance dynamic chart rendering, single codebase for iOS/Android. |
| **`DEC-002`** | [ADR-002](adr/ADR-002-backend-framework.md) | Backend Framework: Python 3.12 + FastAPI | `Proposed` | Async performance, Pydantic v2 schema validation, native financial library support. |
| **`DEC-003`** | [ADR-003](adr/ADR-003-data-stores-separation-of-duties.md) | DB Separation: PostgreSQL vs Firestore | `Proposed` | PostgreSQL for ACID financial facts/pgvector/RLS; Firestore for real-time mobile chat state listeners. |
| **`DEC-004`** | [ADR-004](adr/ADR-004-async-processing-infrastructure.md) | Async Queue: GCP Cloud Tasks + Pub/Sub | `Proposed` | Serverless targeted worker delivery on Cloud Run without managing dedicated Celery clusters. |
| **`DEC-005`** | [ADR-005](adr/ADR-005-model-provider-abstraction.md) | AI Layer: Capability-Matrix Provider Adapter | `Proposed` | Prevents vendor lock-in; handles failover rules between Anthropic Claude Direct API and GCP Vertex AI. |
| **`DEC-006`** | [ADR-006](adr/ADR-006-document-and-financial-lineage.md) | Financial Lineage: Cell-Level Evidence Mapping | `Proposed` | Helps verify claims against source documents by linking every number to document, page, table, cell coordinates. |
| **`DEC-007`** | [ADR-007](adr/ADR-007-tenant-isolation-strategy.md) | Multi-Tenant Isolation: Defense-in-Depth RLS | `Proposed` | PostgreSQL Row-Level Security (RLS) policies as primary boundary using `app.current_organization_id`. |
| **`DEC-008`** | [ADR-008](adr/ADR-008-financial-calculation-and-decimal-policy.md) | Financial Arithmetic: Multi-Tier Decimal | `Proposed` | Prevents IEEE 754 binary floating-point representation errors across trillion-level figures. |
| **`DEC-009`** | [ADR-009](adr/ADR-009-chartspec-rendering-responsibility.md) | Chart Spec: Client Native Rendering | `Proposed` | Backend emits typed `ChartSpec` JSON bound to `result_dataset_id`; Flutter renders native widgets. |
| **`DEC-010`** | [ADR-010](adr/ADR-010-data-classification-and-model-policy-engine.md) | Security Policy: Centralized `PolicyEngine` | `Proposed` | Evaluates data classification exposure rules (`PUBLIC` to `STRICTLY_CONFIDENTIAL`) prior to model/search calls. |

---

## 3. Unresolved Technical Verification Items

1. **`VERIFY-001`**: Confirm KAP (Public Disclosure Platform) automated disclosure retrieval policies and domain scraping rules. (`Status: Pending Validation`)
2. **`VERIFY-002`**: Measure Cloud Run cold-start latencies with Python 3.12 container images under minimum instance = 1 configuration. (`Status: Pending Validation`)
3. **`VERIFY-003`**: Confirm specific commercial licensing terms for Flutter dynamic chart packages (`syncfusion_flutter_charts` vs open-source `fl_chart`). (`Status: Pending Validation`)
4. **`VERIFY-004`**: Legal and compliance signoff on `europe-west1` GCP deployment region for KVKK cross-border data transfer compliance. (`Status: Pending Validation`)
