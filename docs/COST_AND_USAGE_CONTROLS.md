# Finance Intelligence — Cost Management & Usage Controls

> **Document ID**: `CST-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. Token Budgeting & Cost Attribution

To prevent unexpected API expenditure spikes or denial-of-wallet attacks, the system implements cost attribution and token quotas enforced by the `PolicyEngine` and Redis rate-limiters:

1. **Per-User Daily Budget**: Cap of 100,000 LLM input tokens and 20,000 output tokens per user per day.
2. **Per-Organization Monthly Budget**: Default budget cap of $250.00 USD equivalent in API token burn. Reaching 80% triggers an admin warning alert; reaching 100% pauses non-essential LLM summary generation while preserving basic SQL metric queries.
3. **Cost Attribution Tagging**: Every `ModelInvocation` audit log record attributes exact token counts (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`) and calculated USD cost to `user_hash` and `org_hash`.

---

## 2. Prompt Caching Strategy & Measurable Evaluation Targets

> [!NOTE]
> Cost savings from prompt caching are an **evaluable target hypothesis**, subject to ongoing measurement against real prompt profiles.

### Measurable Caching Metrics & Targets
* **Cache-Eligible Input Ratio Target**: Target > 70% of prompt tokens residing in static system instructions and schema blocks marked with `cache_control: {"type": "ephemeral"}`.
* **Cache Hit Rate Target**: Target > 80% cache hit rate on multi-turn conversations.
* **Provider Pricing Structure**: Cached input reads are billed at 10% of standard prompt cost (Anthropic pricing tier); cache creation writes are billed at 125%.
* **Measurement Period**: Weekly aggregated Cloud Monitoring evaluation.
* **Baseline vs. Target**: Baseline without caching = $0.003 / 1k input tokens. Target with caching = $0.0003 / 1k cached input tokens.
* **Alert Threshold**: Alert operations team if prompt cache hit rate drops below 50% over a 24-hour window.

---

## 3. Rate Limits, Concurrency & Circuit Breakers

| Mechanism | Target Resource | Limit Threshold | Action on Exceeded Limit |
|---|---|---|---|
| **API Request Limiter** | FastAPI Router | 60 requests / minute per user | HTTP 429 Too Many Requests |
| **Document Upload Quota** | Storage Service | 500 MB / day per organization | HTTP 429 Upload Limit Reached |
| **Analysis Job Concurrency** | Cloud Tasks Queue | Max 5 concurrent active jobs per user | Queue job with `status='queued'` |
| **Agent Tool Step Cap** | Orchestrator FSM | Max 8 tool calls per analysis task | Terminate agent loop; generate partial result |
| **LLM Provider Circuit Breaker** | External LLM API | > 5% 5xx errors or latency > 15s over 2 min | Trip breaker; fallback to secondary model provider |

---

## 4. Emergency Kill-Switches & Feature Flags

1. `DISABLE_EXTERNAL_LLM_RETRIEVAL`: Immediately halts all outbound web search tool calls.
2. `FORCE_DETERMINISTIC_ONLY`: Disables generative text summary generation, returning raw canonical `TableSpec` and `ChartSpec` JSON payloads directly to the client.
3. `SUSPEND_ORGANIZATION_PROCESSING`: Disables processing for a compromised or over-budget organization tenant.
