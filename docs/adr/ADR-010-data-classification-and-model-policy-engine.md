# ADR-010: Data Classification & Model Policy Engine

* **Decision ID**: `ADR-010`
* **Status**: `Proposed`
* **Context**: Enterprise financial platforms handle data across varying sensitivity levels (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `STRICTLY_CONFIDENTIAL`, `PERSONAL_DATA`). Security policy must enforce strict controls over which data classes can be transmitted to external LLM providers or web search APIs.
* **Decision**: Implement a Centralized **Policy Engine (`PolicyEngine`)**:
  * Every document, chunk, extracted fact, and query is assigned a mandatory Data Classification tag.
  * Prior to executing an external LLM call, vector embedding generation, web search retrieval, or report export, the orchestrator invokes `PolicyEngine.evaluate()`.
  * External LLM transmission of `STRICTLY_CONFIDENTIAL` or raw `PERSONAL_DATA` is **STRICTLY BLOCKED** at the edge.
* **Rationale**: Replaces scattered conditional logic across service modules with a single, audited, unit-tested Policy Decision Point (PDP).
* **Alternatives Considered**:
  1. *Ad-Hoc Conditional Logic*: High risk of developer oversight leading to unauthorized data exfiltration.
  2. *Hardcoded Global Block*: Prevents legitimate analysis of public regulatory disclosures and opt-in internal corporate filings.
* **Security Impact**: Supports compliance with enterprise security boundaries and privacy regulations (KVKK / GDPR).
* **Data Integrity Impact**: Prevents sensitive proprietary facts from leaking into external model provider prompts.
* **MVP Impact**: Provides testable governance boundaries for all 14 Bounded Tools.
* **Cost Impact**: Negligible CPU overhead for local policy rule evaluation.
* **Scalability Impact**: Policy evaluation is a fast in-memory operation (sub-1ms execution).
* **Risks**: Overly restrictive default policy rules blocking valid user query flows (mitigated by clear user error messages).
* **Revisit Trigger**: Integration of local self-hosted open-source LLMs enabling processing of `STRICTLY_CONFIDENTIAL` data on-premise.
