# Finance Intelligence — Architectural Decision Records (ADR Repository)

> **Status**: Active ADR Index (`Draft — Pending Phase 0 User Review`)  
> **Classification**: `INTERNAL`

This directory contains the formal Architectural Decision Records (ADRs) governing the **Finance Intelligence** platform design and infrastructure backbone.

---

## 📋 ADR Catalog Index

| ADR ID | Title | Status | Primary Decision |
|---|---|---|---|
| 001 | [ADR-001: Mobile Technology Selection](ADR-001-mobile-technology-stack.md) | `Proposed` | Adopt Flutter 3.x with Riverpod 2.x for cross-platform mobile client. |
| 002 | [ADR-002: Backend Framework Selection](ADR-002-backend-framework.md) | `Proposed` | Adopt Python 3.12 + FastAPI + Pydantic v2 for API Gateway & Services. |
| 003 | [ADR-003: Primary Data Store & Firestore Duty Separation](ADR-003-data-stores-separation-of-duties.md) | `Proposed` | PostgreSQL 16 for ACID financial facts/pgvector/RLS; Firestore for mobile chat state sync. |
| 004 | [ADR-004: Asynchronous Processing Infrastructure](ADR-004-async-processing-infrastructure.md) | `Proposed` | Adopt GCP Cloud Tasks for targeted HTTP worker job delivery. |
| 005 | [ADR-005: Model Provider Abstraction Architecture](ADR-005-model-provider-abstraction.md) | `Proposed` | Capability-matrix provider adapter interface (Anthropic / GCP Vertex AI). |
| 006 | [ADR-006: Document & Financial Data Lineage](ADR-006-document-and-financial-lineage.md) | `Proposed` | Mandate 6-tier cell-level evidence mapping for every extracted fact and claim. |
| 007 | [ADR-007: Multi-Tenant Isolation Strategy](ADR-007-tenant-isolation-strategy.md) | `Proposed` | Defense-in-depth tenant isolation with PostgreSQL RLS (`app.current_organization_id`) as primary boundary. |
| 008 | [ADR-008: Financial Calculation & Decimal Precision Policy](ADR-008-financial-calculation-and-decimal-policy.md) | `Proposed` | Multi-tier Decimal arithmetic in pure Python Calculation Engine. |
| 009 | [ADR-009: ChartSpec Specification & Rendering Responsibility](ADR-009-chartspec-rendering-responsibility.md) | `Proposed` | Backend emits typed `ChartSpec` JSON bound to `result_dataset_id`; Flutter renders native client widgets. |
| 010 | [ADR-010: Data Classification & Model Policy Engine](ADR-010-data-classification-and-model-policy-engine.md) | `Proposed` | Centralized `PolicyEngine` evaluates classification exposure prior to model/search calls. |
