# ADR-004: Asynchronous Processing Infrastructure

* **Decision ID**: `ADR-004`
* **Status**: `Proposed`
* **Context**: Document ingestion, PDF table parsing, OCR fallback, vector embedding generation, and report export jobs are background processes that exceed synchronous HTTP request timeout bounds.
* **Decision**: Adopt **GCP Cloud Tasks** as the primary asynchronous command delivery infrastructure for MVP:
  * **Cloud Tasks Role**: Dispatches targeted HTTP task requests to background Cloud Run worker endpoints, managing rate controls and retry schedules.
  * **Application-Level Idempotency**: Worker handlers MUST enforce application-level idempotency using deduplication keys (`X-Idempotency-Key` or document version hash) to safely handle at-least-once delivery.
  * **Application-Level Failed Job Tracking**: Failed job attempts are persisted in application-level database tables (`failed_job` / `job_attempt`). When the retry budget is exhausted, the application updates the job status to `failed` or `awaiting_review`.
  * **Controlled Operational Re-execution**: Retrying exhausted jobs or re-triggering failed extraction pipelines is executed as a controlled administrative action via admin API endpoints.
  * **Pub/Sub Role**: Pub/Sub domain event broadcasting is deferred outside MVP unless an ingestion event strictly requires multiple concurrent subscribers.
* **Service Limits (`Pending Validation`)**: Specific Cloud Run HTTP execution timeouts, queue dispatch rates, and task queue constraints are linked to `DECISION_LOG.md` as `Pending Validation` items pending staging benchmarks.
* **Rationale**: GCP Cloud Tasks provides targeted HTTP job dispatch with rate control and auto-scaling execution on Cloud Run without managing dedicated Celery/Redis cluster infrastructure.
* **Alternatives Considered**:
  1. *Celery + Redis*: Operational complexity of maintaining persistent Redis nodes and worker processes on Cloud Run.
  2. *Pub/Sub Only*: Lacks targeted HTTP request pacing and per-task queue management required for user upload jobs.
* **Security Impact**: Worker invocation endpoints are protected via GCP IAM service-to-service authentication.
* **Data Integrity Impact**: Application-level idempotency prevents double-processing of financial files.
* **MVP Impact**: Serverless pay-per-use architecture reduces initial infrastructure cost.
* **Cost Impact**: Zero cost when queue is idle; scales automatically on task spikes.
* **Scalability Impact**: Workers scale independently on Cloud Run.
* **Risks**: Tasks exceeding HTTP request timeouts require Cloud Run Jobs or Batch tasks.
* **Revisit Trigger**: Task execution times routinely exceed worker HTTP timeouts or require multi-consumer event fanout.
