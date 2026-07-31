# Finance Intelligence — Document Ingestion & Multi-Format Parsing Strategy

> **Document ID**: `ING-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. Multi-Layer Extraction & Pipeline Architecture

The Document Ingestion Pipeline processes user-uploaded financial filings (PDF, XLSX, CSV) and transforms raw files into normalized, searchable financial facts with evidence lineage.

```mermaid
flowchart TD
    Upload[1. GCS Direct Upload via Signed URL] --> MIME[2. Magic Byte MIME Validation & Virus Scan]
    MIME --> Hash[3. Server-side SHA-256 Hashing & Deduplication Check]
    Hash --> FormatCheck{Format Type?}

    FormatCheck -->|PDF| LayeredPDF[4a. Layered PDF Extraction Strategy]
    FormatCheck -->|XLSX / CSV| TableExtract[4b. Native OpenPyXL / Pandas / Chardet Parser]

    LayeredPDF --> OCR_Check{Confidence < 0.85 OR Text Density < 50 chars/page?}
    OCR_Check -->|YES| OCR_Engine[5. Cloud Vision / Tesseract OCR Fallback]
    OCR_Check -->|NO| Chunking[6. Structural Table & Text Chunking]
    OCR_Engine --> Chunking
    TableExtract --> Chunking

    Chunking --> Embedding[7. Vector Embedding Generation (pgvector)]
    Chunking --> FactExtraction[8. Financial Fact Extraction & Normalization]
    FactExtraction --> QualityCheck{Extraction Confidence > 0.85?}

    QualityCheck -->|PASS| Store[9. Save to PostgreSQL financial_facts]
    QualityCheck -->|FAIL| ReviewQueue[10. Route to FLAGGED_CONFLICT Human Review]
```

---

## 2. Multi-Candidate PDF & Table Parser Strategy

Rather than relying on a single hardcoded library, the extraction engine employs a candidate strategy evaluated against a golden document benchmark:

1. **Native Text & Layout Extraction Candidates**: `PyMuPDF` (fast C-based rendering), `pdfplumber` (exact character positioning).
2. **Tabular Data Extraction Candidates**: `pdfplumber`, `Camelot`, `Unstructured`.
3. **XLSX Native Workbook Parsing**: `openpyxl` / `pandas` preserving sheet structure, formulas, and numeric formatting.
4. **CSV Dialect & Encoding Detection**: `chardet` for UTF-8 / ISO-8859-9 / Windows-1254 detection, `csv.Sniffer` for delimiter detection.
5. **Parser Confidence Scoring**: Every extracted table receives a confidence score (0.0 to 1.0) based on header alignment, cell border integrity, and checksum validation. Tables scoring < 0.85 are routed to human auditor review (`review_status = 'FLAGGED_CONFLICT'`).

---

## 3. Security Controls & Server Checksum Calculation

1. **Server-Computed SHA-256 Checksum**: The backend server computes the SHA-256 hash upon upload completion instead of trusting client-provided claims.
2. **Pre-Ingestion MIME Validation**: Inspection of byte headers (`%PDF-1.`, `PK\x03\x04`) blocks disguised executables.
3. **Decompression Expansion Guard**: Zip bomb protection on XLSX files enforces a maximum 20:1 uncompressed-to-compressed size ratio.

---

## 4. OCR Fallback Strategy

OCR fallback is triggered under specific, measurable threshold conditions:
1. **Low Text Density**: Page contains fewer than 50 extractable text characters.
2. **Scanned Image Page**: Raster images cover > 80% of total page area without an underlying vector text layer.
3. **Font Encoding Corruption**: Extracted text contains > 15% non-printable or corrupt Unicode replacement characters (`\uFFFD`).

---

## 5. Failure Recovery & Dead-Letter Queue (DLQ)

* **Retry Strategy**: 3 attempts with exponential backoff for temporary storage read timeouts.
* **Dead-Letter Queue (`ingestion-dlq`)**: Unparseable or corrupted files are routed to a DLQ for operational review while updating Firestore job status to `failed_with_details`.
