# ADR-003: Primary Data Store & Firestore Duty Separation

* **Decision ID**: `ADR-003`
* **Status**: `Proposed`
* **Context**: The platform processes canonical relational financial facts, document line item evidence, vector similarity embeddings, and transient real-time chat state for mobile clients.
* **Decision**: Adopt a strict separation of duties between **PostgreSQL 16 + pgvector** (Cloud SQL Proposed Baseline) and **Cloud Firestore**:
  * **PostgreSQL**: Primary canonical source-of-truth for normalized financial facts, Decimal values, evidence lineage, vector embeddings, tenant configurations, Row-Level Security (RLS using `app.current_organization_id`), and append-only audit events.
  * **Firestore**: Operational database exclusively for mobile user chat sessions, real-time job execution progress listeners, and transient notification states.
* **Rationale**: PostgreSQL provides ACID transactional properties, Row-Level Security policies, and Decimal arbitrary precision for financial facts, while Firestore provides live listener state synchronization for mobile UIs without polling overhead.
* **Alternatives Considered**:
  1. *Firestore as Primary Source-of-Truth*: Rejected because document databases lack relational integrity, exact Decimal SQL types, and join capabilities needed for complex financial reconciliation.
  2. *PostgreSQL Only*: Rejected because polling PostgreSQL for live mobile UI status updates causes unnecessary DB connection overhead.
* **Security Impact**: PostgreSQL enables Row-Level Security policy enforcement (`app.current_organization_id`).
* **Data Integrity Impact**: Prevents dual source-of-truth conflicts by keeping financial facts strictly inside PostgreSQL.
* **MVP Impact**: Simplifies mobile UI state management via native Firestore listeners.
* **Cost Impact**: Minimizes Cloud SQL connection costs by shifting high-frequency chat updates to Firestore.
* **Scalability Impact**: Disconnects mobile chat websocket load from relational database queries.
* **Risks**: Potential status sync lag between worker updates in PostgreSQL and Firestore.
* **Revisit Trigger**: High-concurrency scale triggers requirement for dedicated Redis Pub/Sub state sync.
