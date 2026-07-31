# ADR-002: Backend Framework Selection (Python 3.12 + FastAPI)

* **Decision ID**: `ADR-002`
* **Status**: `Proposed`
* **Context**: The backend control plane must orchestrate async document ingestion, process financial formulas, handle Pydantic schema validation, interface with LLM provider APIs, and serve SSE progress streams.
* **Decision**: Adopt **Python 3.12** with **FastAPI**, **Pydantic v2**, **SQLAlchemy 2 (Async)**, and **Alembic**.
* **Rationale**: Python is the primary ecosystem for financial data libraries (`decimal`), PDF layout extraction candidates, vector processing, and LLM SDK integration. FastAPI provides ASGI async execution and automatic OpenAPI documentation generation.
* **Risk Reduction & Limitations**: Pydantic v2 validation filters malformed request bodies and type coercion errors. However, Pydantic validation does not prevent logical data inconsistencies, unauthorized access attempts, or malicious prompt injection payloads inside valid string fields.
* **Alternatives Considered**:
  1. *Node.js / TypeScript*: Lack of arbitrary-precision `Decimal` native math primitives and inferior PDF layout parsing libraries.
  2. *Go*: Slower iteration speed for LLM orchestration and data processing library integration.
* **Security Impact**: Pydantic v2 schema validation filters malformed JSON payload structures.
* **Data Integrity Impact**: Python's native `decimal.Decimal` module prevents binary floating-point representation artifacts.
* **MVP Impact**: Rapid prototyping and rich ecosystem of extraction libraries.
* **Cost Impact**: Standard Cloud Run execution footprint; low memory overhead on Python 3.12.
* **Scalability Impact**: Horizontal auto-scaling on Cloud Run.
* **Risks**: CPU-bound table extraction could block async event loop if not offloaded to Cloud Tasks background workers.
* **Revisit Trigger**: Workload shifts toward high-throughput low-latency streaming requiring Rust/Go microservices.
