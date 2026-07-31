# Finance Intelligence — REST & Realtime API Contracts

> **Document ID**: `API-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Base URL**: `https://api.finance-intelligence.internal/v1`  
> **Classification**: `INTERNAL`

---

## 1. Global API Standards

### 1.1 Mandatory HTTP Request Headers

All incoming requests to the API Gateway MUST include the following standard headers:

```http
Authorization: Bearer <Firebase_ID_Token>
X-Firebase-AppCheck: <Firebase_AppCheck_Token>
X-Correlation-ID: 72868d7f-320c-40af-850f-1077e9dd3360
X-Idempotency-Key: 9b1deb4d-3b7d-414c-9f72-a42e5d774431
Content-Type: application/json
```

* **Server-Injected Context**: The API Gateway validates tokens and constructs an `ExecutionContext` (`authenticated_user_id`, `active_organization_id`, `roles`, `permissions`). Tenant IDs are NEVER accepted from client query bodies or LLM tool arguments.

### 1.2 Standard Error Response Envelope

All API errors return an HTTP 4xx/5xx status code with a uniform JSON envelope:

```json
{
  "error": {
    "code": "POLICY_DENIED_CLASSIFICATION",
    "message": "Target document contains STRICTLY_CONFIDENTIAL metrics which are prohibited from external retrieval processing.",
    "details": [
      {
        "field": "document_ids[0]",
        "issue": "Document classification (STRICTLY_CONFIDENTIAL) violates external analysis policy."
      }
    ],
    "correlation_id": "72868d7f-320c-40af-850f-1077e9dd3360",
    "timestamp": "2026-07-29T17:17:35Z"
  }
}
```

---

## 2. Document Upload API Flow

### 2.1 `POST /v1/documents/upload-url` (Request Pre-Signed Upload Target)

**Request Payload:**
```json
{
  "filename": "Q4_2025_BankA_Financial_Filing.pdf",
  "file_type": "PDF",
  "file_size_bytes": 14258900,
  "data_classification": "CONFIDENTIAL"
}
```

**Success Response (HTTP 200 OK):**
```json
{
  "document_id": "c1f7a8e2-4521-4f8a-981c-99d8213601a0",
  "document_version_id": "a9b8c7d6-1234-4567-8901-abcdef123456",
  "upload_url": "https://storage.googleapis.com/docs-primary/tenants/org_123/documents/c1f7a8e2.pdf?Expires=1785334402&Signature=...",
  "expires_in_seconds": 900,
  "required_headers": {
    "Content-Type": "application/pdf"
  }
}
```

### 2.2 `POST /v1/documents/confirm` (Confirm Upload & Server Compute Checksum)

**Request Payload:**
```json
{
  "document_id": "c1f7a8e2-4521-4f8a-981c-99d8213601a0",
  "document_version_id": "a9b8c7d6-1234-4567-8901-abcdef123456"
}
```

**Success Response (HTTP 202 Accepted):**
```json
{
  "document_id": "c1f7a8e2-4521-4f8a-981c-99d8213601a0",
  "status": "PROCESSING",
  "server_computed_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "ingestion_job_id": "job_ingest_8839201"
}
```

---

## 3. Analysis Job API Flow

### 3.1 `POST /v1/analysis/jobs` (Submit Financial Query)

**Request Payload:**
```json
{
  "query_text": "Türkiye'de aktif büyüklüğüne göre ilk iki bankayı son çeyrek itibarıyla karşılaştır ve sermaye yeterlilik oranlarını rasyo ve grafikle göster.",
  "conversation_id": "conv_99201a88",
  "filters": {
    "institution_codes": ["GARAN", "AKBNK"],
    "period_types": ["QUARTERLY"],
    "years": [2025],
    "quarters": [4],
    "reporting_basis": "CONSOLIDATED"
  },
  "document_ids": ["c1f7a8e2-4521-4f8a-981c-99d8213601a0"]
}
```

**Success Response (HTTP 202 Accepted):**
```json
{
  "job_id": "job_anl_44019283",
  "status": "queued",
  "created_at": "2026-07-29T17:17:35Z",
  "sse_stream_url": "https://api.finance-intelligence.internal/v1/analysis/jobs/job_anl_44019283/stream"
}
```

### 3.2 `GET /v1/analysis/jobs/{job_id}/result` (Retrieve Canonical Results)

**Success Response (HTTP 200 OK):**
```json
{
  "job_id": "job_anl_44019283",
  "result_dataset_id": "ds_88102934-1234-4567-8901-abcdef123456",
  "status": "completed",
  "executive_summary": "Son ortak çeyrek (2025/Q4) itibarıyla, GARAN ve AKBNK konsolide aktif büyüklükleri ve Sermaye Yeterlilik Oranları (SYO) karşılaştırılmıştır. GARAN'ın toplam aktifleri 2.850.000.000.000,00 TRY seviyesinde gerçekleşirken, AKBNK'nin toplam aktifleri 2.610.000.000.000,00 TRY olarak gerçekleşmiştir. GARAN'ın sermaye yeterlilik oranı %18,45 iken, AKBNK'nin sermaye yeterlilik oranı %19,10 seviyesindedir [EIV-001][EIV-002].",
  "table_spec": {
    "result_dataset_id": "ds_88102934-1234-4567-8901-abcdef123456",
    "title": "Banka Karşılaştırma Tablosu (2025/Q4 Konsolide)",
    "headers": ["Metrik", "GARAN", "AKBNK", "Fark", "Birim"],
    "rows": [
      {
        "metric_code": "total_assets",
        "label": "Toplam Aktifler",
        "values": ["2.850.000.000.000,00", "2.610.000.000.000,00", "+240.000.000.000,00", "TRY"],
        "evidence_ids": ["EIV-001", "EIV-002"]
      },
      {
        "metric_code": "capital_adequacy_ratio",
        "label": "Sermaye Yeterlilik Oranı",
        "values": ["18.45%", "19.10%", "-0.65%", "%"],
        "evidence_ids": ["EIV-003", "EIV-004"]
      }
    ]
  },
  "chart_specs": [
    {
      "result_dataset_id": "ds_88102934-1234-4567-8901-abcdef123456",
      "chart_id": "chart_syo_comparison",
      "chart_type": "grouped_bar",
      "title": "Sermaye Yeterlilik Oranı ve Toplam Aktif Karşılaştırması",
      "x_axis": {"label": "Kurumlar", "categories": ["GARAN", "AKBNK"]},
      "y_axis": {"label": "Oran (%)", "min_value": 0, "max_value": 25},
      "series": [
        {
          "name": "Sermaye Yeterlilik Oranı (%)",
          "data": [18.45, 19.10]
        }
      ]
    }
  ],
  "evidence": [
    {
      "evidence_id": "EIV-001",
      "document_id": "c1f7a8e2-4521-4f8a-981c-99d8213601a0",
      "document_name": "GARAN_Q4_2025_FR.pdf",
      "page_number": 42,
      "table_name": "Bilanço - Aktif Kalemleri",
      "cell_coordinate": "Row 14, Col 3",
      "raw_text_snippet": "Toplam Aktifler: 2.850.000.000 Bin TL",
      "confidence_score": 0.998
    }
  ],
  "quality_gate_results": {
    "all_passed": true,
    "evaluated_gates": [
      {"gate_id": "GATE_PERIOD_ALIGNMENT", "status": "PASS"},
      {"gate_id": "GATE_CURRENCY_ALIGNMENT", "status": "PASS"},
      {"gate_id": "GATE_PRECISION_DECIMAL", "status": "PASS"},
      {"gate_id": "GATE_CITATION_FAITHFULNESS", "status": "PASS"}
    ]
  }
}
```

---

## 4. Export Job API Flow

### 4.1 `POST /v1/exports/jobs` (Trigger Excel / CSV Export)

**Request Payload:**
```json
{
  "analysis_job_id": "job_anl_44019283",
  "export_format": "XLSX",
  "include_evidence_sheet": true,
  "include_formulas": true
}
```

**Success Response (HTTP 200 OK):**
```json
{
  "export_job_id": "exp_7710294",
  "status": "COMPLETED",
  "download_url": "https://storage.googleapis.com/exports-temp/tenants/org_123/reports/Report_GARAN_AKBNK_2025Q4.xlsx?Expires=...",
  "file_name": "Finance_Intelligence_GARAN_AKBNK_2025Q4.xlsx",
  "expires_in_seconds": 3600
}
```
