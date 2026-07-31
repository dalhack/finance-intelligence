# ADR-005: Model Provider Abstraction Architecture

* **Decision ID**: `ADR-005`
* **Status**: `Proposed`
* **Context**: LLM capabilities, model IDs, pricing structures, and regional availability evolve rapidly. The application must avoid hardcoding vendor-specific model strings or SDKs directly into business domain logic.
* **Decision**: Implement a capability-matrix **Model Provider Abstraction Layer (`ModelProviderAdapter`)** supporting:
  1. Direct Anthropic Messages API (`AnthropicClaudeDirectAdapter`)
  2. GCP Vertex AI Anthropic Endpoint (`GCPVertexAIClaudeAdapter`)
* **Capability Matrix & Failover Rules**: Automatic failover between model providers is NOT assumed to be equivalent or automatic. Failover is permitted **ONLY IF** data classification policy, data locality (`europe-west1`), prompt caching support, and quality benchmarks match.
* **Rationale**: Provider adapters decouple application code from specific vendor APIs, enabling model provider switching for compatible capabilities while supporting structured tool calls.
* **Alternatives Considered**:
  1. *Direct Unabstracted SDK Integration*: High vendor lock-in risk.
  2. *LangChain / LlamaIndex*: Heavyweight abstractions, unstable API breaking changes, and lack of fine-grained control over prompt caching and tool JSON schemas.
* **Security Impact**: Isolates secret API keys within provider adapter configuration modules backed by GCP Secret Manager.
* **Data Integrity Impact**: Enforces Pydantic strict JSON Schema output validation across all provider adapters.
* **MVP Impact**: Allows starting with Anthropic Direct API and evaluating GCP Vertex AI for enterprise compliance.
* **Cost Impact**: Enables routing requests to lower-cost model tiers or leveraging prompt caching.
* **Scalability Impact**: Supports load distribution across multiple cloud model quotas.
* **Risks**: Variations in structured tool call parsing behavior between providers.
* **Revisit Trigger**: Requirement emerges to support self-hosted open-weight models (e.g. Llama-3/Mistral) on-premise.
