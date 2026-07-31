# ADR-006: Document & Financial Data Lineage

* **Decision ID**: `ADR-006`
* **Status**: `Proposed`
* **Context**: Financial analysts and legal auditors require verifiable evidence for every metric, ratio, and claim presented in analysis reports. Uncited or speculative numerical assertions are unacceptable.
* **Decision**: Mandate a 6-tier cell-level **Evidence Lineage Data Architecture**:
  * Every extracted fact in `financial_facts` and calculated result in `Calculation` MUST link to an `Evidence` record specifying: `Document ID` -> `Version` -> `Page Number` -> `Table Name` -> `Cell Coordinate` -> `Raw Snippet`.
* **Rationale**: Reduces hallucination risk by enforcing that no metric can be marked `completed` without explicit structural proof in the source document.
* **Alternatives Considered**:
  1. *Document-Level Citation Only*: Citing an entire 100-page PDF report does not provide sufficient granularity for balance sheet audit verification.
  2. *LLM Self-Reported Citations*: LLMs can invent page numbers or cell coordinates when not backed by deterministic parser metadata.
* **Security Impact**: Evidence records respect source document data classification access controls.
* **Data Integrity Impact**: Provides auditability from raw PDF upload to final mobile screen display.
* **MVP Impact**: Powers the interactive Evidence Drill-Down Drawer in the Flutter mobile application.
* **Cost Impact**: Marginal database storage overhead for `Evidence` table records.
* **Scalability Impact**: Indexes on `evidence_id` and `document_version_id` ensure fast citation lookups.
* **Risks**: Increased parsing complexity for unstructured non-tabular narrative text.
* **Revisit Trigger**: Audit requirements demand character-level bounding box highlight polygons.
