# Architecture Decision Record: Model Provider Secret Manager Selection

- **Status**: PENDING_USER_SELECTION
- **Date**: 2026-07-31
- **Gate Status**: `SECRET_MANAGER_REAL_INTEGRATION_GATE = BLOCKED_BY_PLATFORM_SELECTION`

---

## 1. Context & Business Need
Finance Intelligence requires zero-trust, automated secret resolution for AI model provider credentials (e.g. Anthropic API keys) without embedding secrets in environment files, source code, CI artifacts, or application logs.

---

## 2. Option Trade-off Evaluation Matrix

| Criterion | GCP Secret Manager | AWS Secrets Manager | HashiCorp Vault | Environment Injection (App Hosting) |
| :--- | :--- | :--- | :--- | :--- |
| **Deployment Alignment** | Native on GCP / Firebase App Hosting | High if AWS ECS / EKS | Cloud-agnostic | Universal across all PaaS |
| **Workload Identity** | IAM Service Account / OIDC | AWS IAM Workload Identity | Kubernetes ServiceAccount / AppRole | Managed Platform IAM |
| **Secret Rotation** | Automated pub/sub rotation | Lambda rotation support | Built-in lease engine | Manual redeployment |
| **Audit Capabilities** | GCP Cloud Audit Logs | AWS CloudTrail | Central Audit Log Stream | Platform Build Logs |
| **Regionality** | Multi-region & Regional | Regional with replication | Multi-datacenter cluster | Platform dependent |
| **Operational Burden** | Very Low (Serverless) | Very Low (Serverless) | High (Cluster maintenance) | Zero |
| **Local Dev Alignment** | Local Emulator / GCloud CLI | LocalStack | Local Vault container | `EnvironmentSecretResolver` |
| **Failure Mode** | Fail-Closed `PROVIDER_SECRET_UNAVAILABLE` | Fail-Closed `PROVIDER_SECRET_UNAVAILABLE` | Fail-Closed `PROVIDER_SECRET_UNAVAILABLE` | Fail-Closed `PROVIDER_SECRET_UNAVAILABLE` |

---

## 3. Security Rules & Non-Negotiables
1. Secrets MUST NOT be logged in application logs, exception tracebacks, or HTTP response headers.
2. Secrets MUST NOT be serialized into Pydantic models or Riverpod state.
3. Secrets MUST be resolved at invocation time using `ProviderSecretResolver`.
4. Blank or whitespace secret values MUST raise `PROVIDER_SECRET_UNAVAILABLE` immediately.

---

## 4. Final Recommendation & Next Steps
Pending platform cloud environment confirmation by project stakeholder.
