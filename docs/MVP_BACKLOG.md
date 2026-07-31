# Finance Intelligence — MVP Product Backlog & Story Catalog

> **Document ID**: `BCK-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. Governance & Execution Criteria

### Definition of Ready (DoR)
A story is Ready for sprint planning ONLY when:
1. Requirements are unambiguous with explicit Acceptance Criteria.
2. Target API contracts, JSON schemas, or DB schema changes are documented in `docs/`.
3. Security and Data Classification impact is assessed via `PolicyEngine` rules.
4. Fibonacci story points are estimated by the engineering team.

### Definition of Done (DoD)
A story is Done ONLY when:
1. Code is written, reviewed, and merged without bypassing lint/type checks.
2. Unit test coverage meets minimum threshold (>= 85% for calculation engine).
3. Quality gates and security checks pass clean.
4. API contracts and documentation are updated.
5. Automated integration test demonstrates clean execution on Cloud Run staging.

---

## 2. Epics & User Story Backlog

### Epic 1: Security, Auth & Multi-tenant Core
* **`STORY-1.1`**: Implement Firebase Auth & App Check middleware on FastAPI Gateway.
  * *Estimate*: 5 pts | *Priority*: P0
  * *Acceptance Criteria*: Gateway validates Bearer token and App Check token. Unsigned requests receive HTTP 401/403.
* **`STORY-1.2`**: Implement `PolicyEngine` and Data Classification exposure check.
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: `CONFIDENTIAL` metrics block external retrieval calls unless opt-in policy is flagged.
* **`STORY-1.3`**: PostgreSQL Row-Level Security (RLS) defense-in-depth isolation policies (`app.current_organization_id`) & SQLAlchemy pool cleanup hooks.
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: RLS policies active on all tenant tables; `db_app_user` has `NOBYPASSRLS`; pool hooks execute `RESET app.current_organization_id`.

### Epic 2: Document Ingestion & Multi-Format Parsing Pipeline
* **`STORY-2.1`**: GCS Signed URL pre-upload endpoint & server-computed SHA-256 hash.
  * *Estimate*: 5 pts | *Priority*: P0
  * *Acceptance Criteria*: Clients fetch 15-min signed PUT URL. Server computes SHA-256 hash upon upload completion.
* **`STORY-2.2`**: Candidate PDF & XLSX layout table extractor worker with confidence scoring.
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: Extract table cells from quarterly PDFs/XLSX with confidence score; tables < 0.85 routed to human review.
* **`STORY-2.3`**: Ingestion OCR fallback engine & DLQ retry policy.
  * *Estimate*: 5 pts | *Priority*: P1
  * *Acceptance Criteria*: Text density < 50 chars/page triggers OCR fallback; unparseable files routed to DLQ.

### Epic 3: Financial Calculation Engine & Fact Store
* **`STORY-3.1`**: `FinancialFact` PostgreSQL schema & multi-tier Decimal normalizer.
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: Scale normalization executed without floating-point errors; raw strings preserved.
* **`STORY-3.2`**: Formula Registry implementation for 11 MVP metrics.
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: Formulas for CAR, ROA, ROE, LDR, NIM compute 100% match against gold Excel models.
* **`STORY-3.3`**: Metric reconciliation and conflict status state machine (`review_status`).
  * *Estimate*: 5 pts | *Priority*: P1
  * *Acceptance Criteria*: Discrepancies > 0.01% flag fact as `FLAGGED_CONFLICT` for human review.

### Epic 4: LLM Orchestration & Bounded Tools
* **`STORY-4.1`**: Capability-Matrix Model Provider Abstraction (Anthropic Claude API & Vertex AI).
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: FSM orchestrator invokes tools via JSON Schema contracts without client tenant args; handles regional data residency failover rules.
* **`STORY-4.2`**: Implement 14 Bounded Tool Handlers with server-injected `ExecutionContext`.
  * *Estimate*: 13 pts | *Priority*: P0
  * *Acceptance Criteria*: All 14 tools execute strictly bounded JSON queries with zero client tenant IDs; `query_regulations` returns explicit `REGULATORY_DATA_UNAVAILABLE` error in MVP.
* **`STORY-4.3`**: Indirect Prompt Injection defense & XML tag context isolation.
  * *Estimate*: 5 pts | *Priority*: P0
  * *Acceptance Criteria*: Malicious prompt inside PDF fails to break LLM out of structured tool execution mode.

### Epic 5: Mobile App UI & Client Visualization
* **`STORY-5.1`**: Flutter Riverpod Clean Architecture skeleton & GoRouter setup.
  * *Estimate*: 5 pts | *Priority*: P0
  * *Acceptance Criteria*: Mobile client initializes Firebase App Check and renders main query dashboard.
* **`STORY-5.2`**: Native `ChartSpec` visualizer widget implementation bound to `result_dataset_id`.
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: Client dynamically renders horizontal, vertical, grouped bar, line, stacked bar, and pie charts from `ChartSpec` JSON.
* **`STORY-5.3`**: Realtime Analysis Progress SSE listener widget.
  * *Estimate*: 5 pts | *Priority*: P0
  * *Acceptance Criteria*: UI displays step-by-step progress state transitions (`retrieving` ➔ `calculating` ➔ `completed`).

### Epic 6: Evidence & Quality Gates
* **`STORY-6.1`**: Automated Quality Gate Suite execution engine.
  * *Estimate*: 8 pts | *Priority*: P0
  * *Acceptance Criteria*: Analysis job separates `completed_with_warnings` from blocking `FAILED` states.
* **`STORY-6.2`**: Evidence Drill-Down Drawer in Flutter UI.
  * *Estimate*: 5 pts | *Priority*: P0
  * *Acceptance Criteria*: Tapping `[EIV-001]` opens drawer displaying PDF page preview and table cell coordinates.

### Epic 7: Report Export & Audit Integrity
* **`STORY-7.1`**: XLSX / CSV canonical export worker with formula preservation.
  * *Estimate*: 5 pts | *Priority*: P1
  * *Acceptance Criteria*: Export generates structured Excel workbook with active calculation formulas and evidence tab.
* **`STORY-7.2`**: Append-only `AuditEvent` hash-chain logger with pseudonymized IDs.
  * *Estimate*: 5 pts | *Priority*: P0
  * *Acceptance Criteria*: Every analysis job writes tamper-evident audit record to PostgreSQL using `user_hash` and `org_hash`.
