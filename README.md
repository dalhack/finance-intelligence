# Finance Intelligence

> **Enterprise Financial Analysis & Reporting Platform**  
> *Independent Mobile-First Product Backbone (Phase 1 Baseline)*

---

## 📌 Product Overview

**Finance Intelligence** is a multi-tier enterprise financial analysis platform. It allows financial analysts, executives, and auditors to execute natural-language queries over structured banking filings, balance sheets, and regulatory disclosures.

Key Architectural Guarantees:
* **Strict Multi-Tenant Isolation**: PostgreSQL Row-Level Security (RLS) policies (`app.current_organization_id`) and `FORCE ROW LEVEL SECURITY` on shared-schema tenant-aware tables.
* **Deterministic Calculation Engine**: Multi-tier Decimal math in pure Python (`decimal.getcontext().prec = 38`) avoiding binary floating-point representation artifacts.
* **Granular Lineage**: 6-level cell coordinate mapping from claim to source document page.
* **Client-Side Native Visualizations**: Type-safe `ChartSpec` JSON schemas bound to a canonical `result_dataset_id`.

---

## 📁 Monorepo Structure

```text
finance-intelligence/
├── .env.example              # Server-only vs public client environment configuration
├── .gitignore                # Workspace git ignore rules
├── README.md                 # Master project documentation
├── Makefile                  # Developer workflow automation tasks
├── pyproject.toml            # Isolated Python project definition & dependencies
├── requirements.lock         # Reproducible locked Python dependencies snapshot
├── apps/
│   └── mobile/               # Flutter mobile application (iOS / Android scaffold)
├── services/
│   ├── api/                  # FastAPI control plane service & Alembic RLS migrations
│   └── worker/               # Async worker skeleton
├── packages/
│   ├── contracts/            # Canonical JSON Schemas & OpenAPI wire contracts
│   └── financial_domain/     # Pure Python financial calculation domain package
├── tests/
│   ├── contract/             # Wire contract validation tests
│   ├── integration/          # PostgreSQL & RLS tenant isolation tests
│   └── unit/                 # Unit tests
├── scripts/                  # Boundary verification & secret scanner utilities
└── .github/
    └── workflows/            # GitHub Actions CI workflow skeleton
```

---

## 🔒 Dependency Locking & Reproducibility Strategy

Dependencies are managed in `pyproject.toml` and pinned reproducibly in `requirements.lock`.

### Lock Regeneration Command
```bash
# Regenerate requirements.lock from pyproject.toml using pip-compile
pip install pip-tools
pip-compile --generate-hashes pyproject.toml -o requirements.lock
```

---

## 🛠️ Local Development & Test Setup

### 1. Isolated Local PostgreSQL Instance (Port 5433)
```bash
# Initialize local-only development database cluster
initdb -D .pgdata_dev -A trust -U postgres
pg_ctl -D .pgdata_dev -l .pgdata_dev/postgres.log -o "-p 5433 -k /tmp" start

# Provision test database and segregated roles
psql -h localhost -p 5433 -U postgres -c "CREATE DATABASE finance_intelligence_test;"
psql -h localhost -p 5433 -U postgres -d finance_intelligence_test -c "
  CREATE ROLE db_owner WITH LOGIN PASSWORD 'dev_owner_pass_123';
  CREATE ROLE db_bootstrap WITH LOGIN PASSWORD 'dev_bootstrap_pass_123';
  CREATE ROLE db_app_user WITH LOGIN NOBYPASSRLS PASSWORD 'dev_app_user_pass_123';
  GRANT ALL PRIVILEGES ON DATABASE finance_intelligence_test TO db_owner;
  GRANT CONNECT ON DATABASE finance_intelligence_test TO db_bootstrap, db_app_user;
  GRANT ALL ON SCHEMA public TO db_owner;
  ALTER SCHEMA public OWNER TO db_owner;
"
```

### 2. Set Test Environment Variables
```bash
export TEST_API_DATABASE_URL="postgresql+asyncpg://db_api_user:dev_api_user_pass_123@localhost:5433/finance_intelligence_test"
export TEST_WORKER_DATABASE_URL="postgresql+asyncpg://db_ingestion_worker:dev_worker_pass_123@localhost:5433/finance_intelligence_test"
export TEST_ROUNDTRIP_DATABASE_URL="postgresql+asyncpg://db_owner:dev_owner_pass_123@localhost:5433/finance_intelligence_roundtrip_test"
```

### 3. Run Test Suite
```bash
# Run unit, contract, and PostgreSQL RLS integration tests
pytest tests/
```

### 4. Run Boundary & Secret Scanner
```bash
# Run boundary scanner & secret auditor
python scripts/verify_boundary.py
```
