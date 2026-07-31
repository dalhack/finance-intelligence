# Finance Intelligence — Phase 0 Architecture & Engineering Documentation Hub

Welcome to the **Finance Intelligence** Phase 0 Product Architecture & Application Backbone documentation suite. This hub provides an end-to-end blueprint for an enterprise-grade financial intelligence platform.

> [!IMPORTANT]
> **Status**: `Draft — Pending Phase 0 User Review`  
> All technology selections and design decisions in this phase are `Proposed` and subject to formal review and validation.

---

## 📚 Documentation Index & Recommended Reading Order

### 1. Core Vision & Requirements
* 📋 [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) — Product vision, functional (`FR-*`), non-functional (`NFR-*`), security (`SEC-*`), data (`DATA-*`), AI (`AI-*`), and UX (`UX-*`) requirements with 43 unique IDs.

### 2. Architecture & Design
* 🏗️ [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) — Context, component, container, sequence diagrams (Mermaid), Cloud Run/PostgreSQL/Firestore topology, sync/async flows, and monorepo structure.
* 🛡️ [SECURITY_THREAT_MODEL.md](SECURITY_THREAT_MODEL.md) — STRIDE threat matrix, defense-in-depth tenant isolation (RLS), indirect prompt injection defense, SSRF/retrieval safety, and App Check security boundaries.
* 🔐 [DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md) — `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `STRICTLY_CONFIDENTIAL`, and `PERSONAL_DATA` classifications, model routing matrix, and policy decision engine.

### 3. Data & APIs
* 🗄️ [DATA_MODEL.md](DATA_MODEL.md) — ER diagrams, 33 core entities, PostgreSQL (RLS) vs Firestore responsibility split, audit log tamper-evident schema, and `FinancialFact` data structures.
* 🔌 [API_CONTRACTS.md](API_CONTRACTS.md) — Versioned REST/SSE endpoints, OpenAPI schemas, error envelopes, signed upload flows, and idempotency enforcement.

### 4. Intelligence & Execution Engines
* 🤖 [AGENT_AND_TOOL_DESIGN.md](AGENT_AND_TOOL_DESIGN.md) — LLM orchestration state machine, capability matrix provider abstraction, server-injected execution context, and 14 bounded JSON Schema tool definitions (zero client tenant IDs).
* 📄 [DOCUMENT_INGESTION_DESIGN.md](DOCUMENT_INGESTION_DESIGN.md) — Multi-format parser strategy (PDF layout candidates, XLSX, CSV), layout-aware chunking, hash deduplication, OCR fallback triggers, and confidence scoring.
* 🔢 [FINANCIAL_CALCULATION_ENGINE.md](FINANCIAL_CALCULATION_ENGINE.md) — Formula registry, multi-tier Decimal arithmetic, currency normalization, period semantics, and 11 MVP financial metric definitions.
* 📍 [SOURCE_AND_CITATION_POLICY.md](SOURCE_AND_CITATION_POLICY.md) — 7-tier source authority ranking, claim-to-evidence cell-level mapping, and claim verification rules.

### 5. Client & Operations
* 📱 [MOBILE_UX_FLOW.md](MOBILE_UX_FLOW.md) — Flutter app navigation flow, Riverpod state management, dynamic `ChartSpec` rendering, evidence drill-down drawer, and accessibility.
* 📅 [MVP_BACKLOG.md](MVP_BACKLOG.md) — Epics, user stories, Fibonacci sizing, Definition of Ready (DoR), and Definition of Done (DoD).
* 🗺️ [PHASED_IMPLEMENTATION_PLAN.md](PHASED_IMPLEMENTATION_PLAN.md) — Phase 0 to Phase 6 roadmap with explicit entry/exit criteria and rollback plans.

### 6. Assurance & Governance
* 🧪 [TEST_STRATEGY.md](TEST_STRATEGY.md) — Golden datasets, property-based calculation tests, prompt injection benchmarks, LLM faithfulness evaluation, and CI release gates.
* 💰 [COST_AND_USAGE_CONTROLS.md](COST_AND_USAGE_CONTROLS.md) — Token budgets, prompt caching target metrics, Cloud Run concurrency limits, storage lifecycle, and kill switches.
* 📝 [DECISION_LOG.md](DECISION_LOG.md) — Master log of explicit assumptions (`ASM-001` to `ASM-020`), proposed architectural decisions, and open technical verification items.
* ⚠️ [RISK_REGISTER.md](RISK_REGISTER.md) — Risk matrix (`RSK-001` to `RSK-010`), severity scores, mitigation strategies, and trigger conditions.
* 🔍 [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md) — End-to-end mapping for all 43 PRD requirements to Architecture, APIs, Data Entities, Security Controls, Tests, and Backlog items.
* 🏛️ [ADR Repository](adr/README.md) — 10 Architectural Decision Records covering technology stack choices, database split, calculation precision, and policy enforcement.

---

## 🧭 Reading Path Recommendations

* **For Software & System Architects**: Start with [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) ➔ [DATA_MODEL.md](DATA_MODEL.md) ➔ [ADR Repository](adr/README.md).
* **For Security & Compliance Officers**: Start with [SECURITY_THREAT_MODEL.md](SECURITY_THREAT_MODEL.md) ➔ [DATA_CLASSIFICATION_POLICY.md](DATA_CLASSIFICATION_POLICY.md) ➔ [SOURCE_AND_CITATION_POLICY.md](SOURCE_AND_CITATION_POLICY.md).
* **For Backend & Financial Engineers**: Start with [FINANCIAL_CALCULATION_ENGINE.md](FINANCIAL_CALCULATION_ENGINE.md) ➔ [DOCUMENT_INGESTION_DESIGN.md](DOCUMENT_INGESTION_DESIGN.md) ➔ [API_CONTRACTS.md](API_CONTRACTS.md) ➔ [AGENT_AND_TOOL_DESIGN.md](AGENT_AND_TOOL_DESIGN.md).
* **For Mobile Application Developers**: Start with [MOBILE_UX_FLOW.md](MOBILE_UX_FLOW.md) ➔ [API_CONTRACTS.md](API_CONTRACTS.md) ➔ [MVP_BACKLOG.md](MVP_BACKLOG.md).
* **For QA & Test Engineers**: Start with [TEST_STRATEGY.md](TEST_STRATEGY.md) ➔ [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md).
