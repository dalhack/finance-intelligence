# Finance Intelligence — Source Priority, Evidence Lineage & Citation Policy

> **Document ID**: `CIT-FIN-001`  
> **Status**: `Draft — Pending Phase 0 User Review`  
> **Classification**: `INTERNAL`

---

## 1. 7-Tier Source Priority & Authority Matrix

When resolving conflicting financial figures or citing regulatory claims, the platform adheres to the ordered 7-tier authority hierarchy:

| Priority Rank | Source Tier Type | Authority Score (0-100) | Description & Examples | Verification Requirement |
|---|---|---|---|---|
| **Tier 1** | **Human-Verified Structured Data** | **100** | Manually audited balance sheet facts stamped by organization auditor in PostgreSQL `financial_facts`. | Absolute Authority; overrides unverified extracts. |
| **Tier 2** | **Verified Official Filing** | **95** | User-uploaded or fetched official quarterly audit reports (KAP filings, PDF/XLSX balance sheets). | Server-computed SHA-256 hash match + magic byte validation. |
| **Tier 3** | **Official Investor Relations (IR)** | **90** | Published earnings presentations directly hosted on bank IR portals. | Domain authority check (`*banka.com.tr/ir`). |
| **Tier 4** | **Official Notification Platform** | **85** | Public disclosure notifications published on Public Disclosure Platform (KAP - `kap.org.tr`). | Domain allowlist verification. |
| **Tier 5** | **Regulator / Central Bank** | **85** | Banking Regulation and Supervision Agency (BDDK) and Central Bank (TCMB) bulletins. | Official government domain verification (`*.gov.tr`). |
| **Tier 6** | **Official Gazette / Legislation** | **80** | Resmî Gazete publication text for banking laws. | Official gazette reference validation. |
| **Tier 7** | **Secondary News & Market Data** | **50** | Secondary financial news outlets or unverified secondary web search snippets. | **MUST BE VERIFIED** against Tier 1-5 primary sources before inclusion. |

---

## 2. Source Conflict Resolution Rules

1. **Higher Tier Trumps Lower Tier**: A Tier 2 KAP filing value overrides a Tier 7 secondary news figure.
2. **Same Tier Conflict (Restated Filings)**: If an institution publishes a restated financial report for a past quarter, the file with the most recent `publication_date` and highest `version_number` overrides superseded versions.
3. **Discrepancy Flagging**: If two Tier 2 filings for the same metric/period differ by > 0.01%, the status machine sets `review_status = 'FLAGGED_CONFLICT'` and generates a `DataIssue` record for auditor review.

---

## 3. Evidence Granularity Hierarchy

Every claim, number, ratio, or table cell MUST link back to an `Evidence` record specifying 6 levels of positioning:

```text
Document ID -> Version Number -> Page Number -> Table ID/Name -> Cell/Row Coordinate -> Exact Snippet Text
```

* **Example Evidence Citation Tag**: `[EIV-001]`
* **Resolved Coordinates**: `GARAN_Q4_2025.pdf` | `v1` | `p.42` | `Table 3.1` | `Row 14, Col 3` | `"Toplam Aktifler: 2.850.000.000 Bin TL"`

---

## 4. Automated LLM Claim Verification Engine

Before an analysis response is marked `completed`:
1. **Fact Extraction Parsing**: Regex parses all numerical values asserted in LLM generated text.
2. **Cross-Check Verification**: Each numerical claim is matched against the deterministic output of the Calculation Engine or `financial_facts` table.
3. **Citation Verification**: Any key numerical claim lacking an associated `[EIV-XXXX]` tag or failing cross-check verification triggers Quality Gate rejection (`GATE_CITATION_FAITHFULNESS`), preventing unverified LLM output from reaching the completed state.
