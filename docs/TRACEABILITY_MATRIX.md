# Finance Intelligence — Requirements Traceability Matrix (RTM)

> **Document ID**: `RTM-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. Master Requirements Traceability Table (43 Unique PRD Requirement IDs)

| Requirement ID | Requirement Statement | Architecture Component | API or Tool | Data Entity | Security Control | Verification/Test | Backlog Item | Status | Gap or Remediation |
|---|---|---|---|---|---|---|---|---|---|
| **`FR-001`** | Free-form financial query input up to 4,000 chars | FastAPI Gateway / Orchestrator | `POST /v1/analysis/jobs` | `Message`, `Conversation` | Auth Bearer Token + App Check | `TST-INT-001` | `STORY-4.1` | `Fully Traced` | None |
| **`FR-002`** | PDF/XLSX/CSV table extraction | Document Ingestion Worker | `extract_financial_table` | `DocumentVersion`, `DocumentChunk` | Pre-upload magic byte MIME check | `TST-ING-002` | `STORY-2.2` | `Fully Traced` | Candidate parser benchmark pending |
| **`FR-003`** | Document hash deduplication | Ingestion Pipeline | `POST /v1/documents/confirm` | `DocumentVersion` | Server-computed SHA-256 validation | `TST-ING-001` | `STORY-2.1` | `Fully Traced` | None |
| **`FR-004`** | Extract 11 core financial metrics | Fact Normalizer Engine | `query_financial_facts` | `FinancialFact`, `MetricDefinition` | Multi-tier scale normalization | `TST-DAT-001` | `STORY-3.1` | `Fully Traced` | None |
| **`FR-005`** | Multi-bank peer comparison | Query / Compare Engine | `compare_institutions` | `Institution`, `FinancialFact` | PostgreSQL RLS tenant isolation | `TST-CAL-002` | `STORY-3.3` | `Fully Traced` | None |
| **`FR-006`** | Deterministic metric calculation | Calculation Engine | `calculate_financial_metrics` | `Calculation`, `CalculationInput` | Python Decimal math (`prec=38`) | `TST-CAL-001` | `STORY-3.2` | `Fully Traced` | None |
| **`FR-007`** | Canonical Table & ChartSpecs | Result Formatter | `generate_chart_spec` | `ChartSpec`, `TableSpec` | Tied to `result_dataset_id` | `TST-UI-002` | `STORY-5.2` | `Fully Traced` | None |
| **`FR-008`** | Granular evidence lineage | Evidence Engine | `get_source_evidence` | `Evidence` | Cell coordinate mapping | `TST-CIT-001` | `STORY-6.2` | `Fully Traced` | None |
| **`FR-009`** | Evidence drill-down drawer | Flutter Mobile Client | `GET /v1/analysis/jobs/{id}/result` | `Evidence` | Evidence token verification | `TST-UI-003` | `STORY-6.2` | `Fully Traced` | Proposed client target |
| **`FR-010`** | XLSX / CSV report export | Export Worker | `generate_excel_report` | `ExportJob` | Export permission check | `TST-EXP-001` | `STORY-7.1` | `Fully Traced` | Formula injection sanitizer |
| **`FR-011`** | Regulatory query adapter | Regulatory Module Placeholder | `query_regulations` | `Regulation`, `RegulationVersion` | Public domain check | `TST-REG-001` | `STORY-4.2` | `DEFERRED` | MVP returns `REGULATORY_DATA_UNAVAILABLE` |
| **`FR-012`** | Audit event persistence | Audit Engine | All Endpoints / Tools | `AuditEvent` | Append-only hash chain | `TST-SEC-004` | `STORY-7.2` | `Fully Traced` | Tamper evidence provided |
| **`NFR-001`** | Sync latency < 300ms, SSE init < 2s | FastAPI Gateway / Cloud Tasks | `GET /v1/analysis/jobs/{id}/stream` | `AnalysisJob` | Cloud Run auto-scaling | `TST-PRF-001` | `STORY-1.1` | `PARTIAL` | SSE latency benchmark pending |
| **`NFR-002`** | Cloud Run auto-scaling 0-50 | Cloud Infrastructure | Infrastructure Config | `AnalysisJob` | Cloud Run auto-scale rules | `TST-PRF-002` | `STORY-1.1` | `PARTIAL` | Load testing deferred to Phase 6 |
| **`NFR-003`** | Target 99.9% monthly uptime | Cloud Infrastructure | High Availability Deployment | Infrastructure Config | Cloud SQL regional HA failover | `TST-RES-001` | `STORY-1.1` | `PARTIAL` | Multi-region DR deferred |
| **`NFR-004`** | Prevent floating-point errors | Calculation Engine | `calculate_financial_metrics` | `Calculation` | Python Decimal arithmetic (`prec=38`) | `TST-CAL-003` | `STORY-3.2` | `Fully Traced` | None |
| **`NFR-005`** | Mobile fluid transitions & offline | Flutter Mobile Client | Client Cache Layer | `Message`, `ChartSpec` | Hive / SQLite offline cache | `TST-UI-004` | `STORY-5.1` | `PARTIAL` | Proposed client target |
| **`NFR-006`** | Document file size limit 50MB | Upload Gateway | `POST /v1/documents/upload-url` | `DocumentVersion` | Pre-signed upload size guard | `TST-ING-003` | `STORY-2.1` | `Fully Traced` | None |
| **`SEC-001`** | Firebase Auth & App Check | Edge Gateway Middleware | All Protected Routes | `User` | Bearer Token & Attestation | `TST-SEC-001` | `STORY-1.1` | `Fully Traced` | None |
| **`SEC-002`** | No secrets in client binaries | Build Pipeline | Client Config | Secret Config | Cloud Secret Manager isolation | `TST-SEC-005` | `STORY-1.1` | `Fully Traced` | None |
| **`SEC-003`** | 15-min GCS Signed Upload URLs | Storage Service | `POST /v1/documents/upload-url` | `Document` | Pre-authorization object check | `TST-SEC-006` | `STORY-2.1` | `Fully Traced` | Server computes SHA-256 hash |
| **`SEC-004`** | Magic byte MIME & malware scan | Ingestion Pipeline | Upload Worker | `DocumentVersion` | Pre-ingestion validation | `TST-SEC-007` | `STORY-2.1` | `Fully Traced` | None |
| **`SEC-005`** | Defense-in-depth tenant isolation | PostgreSQL RLS / GCS | All DB Queries & Storage | `Organization` | RLS (`app.current_organization_id`) | `TST-SEC-003` | `STORY-1.3` | `Fully Traced` | `db_app_user` has `NOBYPASSRLS` |
| **`SEC-006`** | SSRF & Domain Allowlist Guard | Web Retrieval Tool | `search_public_sources`, `fetch_official_document` | `Source` | DNS IP check vs RFC 1918 | `TST-SEC-002` | `STORY-4.2` | `Fully Traced` | Max 3 redirects enforced |
| **`SEC-007`** | Indirect Prompt Injection defense | LLM Orchestration Engine | All LLM Provider Calls | `ModelInvocation` | XML tag context isolation | `TST-SEC-008` | `STORY-4.3` | `Fully Traced` | Context tag isolation |
| **`SEC-008`** | Server-injected tenant context | LLM Tool Handlers | All 14 Tools | `ExecutionContext` | Zero LLM tenant arguments | `TST-SEC-009` | `STORY-4.2` | `Fully Traced` | Server-injected ExecutionContext |
| **`SEC-009`** | Log pseudonymization & PII redaction | Logging & Middleware | All Services | `AuditEvent`, `LogEntry` | HMAC `user_hash` & `org_hash` | `TST-SEC-010` | `STORY-7.2` | `Fully Traced` | PII masking engine |
| **`DATA-001`** | 5-level Data Classification | Policy Engine | All Endpoints / Tools | All Entities | PolicyEngine submission check | `TST-POL-001` | `STORY-1.2` | `Fully Traced` | None |
| **`DATA-002`** | Preserve raw original string values | Fact Store | `query_financial_facts` | `FinancialFact` | Unaltered raw string field | `TST-DAT-002` | `STORY-3.1` | `Fully Traced` | None |
| **`DATA-003`** | Explicit exchange rate tracking | Normalization Pipeline | `query_financial_facts` | `FinancialFact` | Central bank rate lineage | `TST-DAT-003` | `STORY-3.1` | `Fully Traced` | None |
| **`DATA-004`** | Append-only audit hash chain | Audit Service | All Actions | `AuditEvent` | Cryptographic hash chain | `TST-DAT-004` | `STORY-7.2` | `Fully Traced` | Provides tamper evidence |
| **`DATA-005`** | Hard deletion with legal hold | Data Lifecycle Service | Maintenance Tasks | `Document`, `FinancialFact` | Storage purge & DB cascade | `TST-DAT-005` | `STORY-1.3` | `Fully Traced` | Legal hold preserves audit hash |
| **`AI-001`** | Capability-matrix model provider | Model Provider Adapter | Internal Orchestrator | `ModelInvocation` | Capability matrix failover | `TST-AI-001` | `STORY-4.1` | `Fully Traced` | Failover rules enforced |
| **`AI-002`** | Bounded tool JSON schemas | Tool Handlers | All 14 Tools | Tool Specs | Strict JSON Schema validation | `TST-AI-002` | `STORY-4.2` | `Fully Traced` | Zero LLM tenant args |
| **`AI-003`** | Deterministic number verification | Quality Gate Engine | `calculate_financial_metrics` | `Calculation` | Number matching vs engine | `TST-AI-003` | `STORY-6.1` | `Fully Traced` | None |
| **`AI-004`** | Inline evidence citation tags | LLM Orchestrator | `get_source_evidence` | `Evidence` | `[EIV-XXXX]` tag verification | `TST-AI-004` | `STORY-6.1` | `Fully Traced` | None |
| **`AI-005`** | Prompt caching cost optimization | LLM Provider Adapter | Internal Orchestrator | `ModelInvocation` | Measurable hit rate targets | `TST-AI-005` | `STORY-4.1` | `PARTIAL` | Evaluation target hypothesis |
| **`UX-001`** | Flutter Clean Architecture | Mobile Client | All Client Screens | N/A | Riverpod 2.x state management | `TST-UI-001` | `STORY-5.1` | `PARTIAL` | Proposed client target |
| **`UX-002`** | Query screen UI layout | Mobile Client | Main Dashboard Screen | `Message` | Prompt input & filter chips | `TST-UI-005` | `STORY-5.1` | `Fully Traced` | Proposed client target |
| **`UX-003`** | Realtime progress execution state | Mobile Client | Analysis Progress Screen | `AnalysisJob` | SSE listener status updates | `TST-UI-006` | `STORY-5.3` | `Fully Traced` | Proposed client target |
| **`UX-004`** | Tabbed analysis results view | Mobile Client | Results Screen | `TableSpec`, `ChartSpec` | Tabbed navigation layout | `TST-UI-007` | `STORY-5.2` | `Fully Traced` | Proposed client target |
| **`UX-005`** | Interactive evidence drawer | Mobile Client | Evidence Drawer Widget | `Evidence` | Evidence drill-down drawer | `TST-UI-008` | `STORY-6.2` | `Fully Traced` | Proposed client target |
| **`UX-006`** | WCAG 2.1 AA accessibility | Mobile Client | All Client Components | N/A | Target 48x48dp tap bounds | `TST-UI-009` | `STORY-5.1` | `DEFERRED` | Accessibility audit in Phase 5 |

---

## 2. RTM Verification & Traceability Summary

* **Total PRD Requirements**: 43
* **Unique Requirements in RTM**: 43
* **Fully Traced**: 35 (81.4%)
* **Partial**: 6 (14.0%) — *Includes performance benchmarks, candidate parser evaluations, and proposed mobile targets awaiting benchmark validation.*
* **Untraced**: 0 (0.0%)
* **Deferred**: 2 (4.7%) — *Includes Regulatory Module (`FR-011`) and WCAG accessibility audit (`UX-006`).*
