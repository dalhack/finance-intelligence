import gc
from io import BytesIO

import pdfplumber
from app.core.config import settings
from app.parsers.base import (
    CanonicalExtractionOutput,
    DocumentParserPort,
    ExtractionWarningItem,
)

# pdfplumber retains the parsed objects of every page it has opened, so walking
# a large filing in one pass grows the resident set past the worker's memory
# limit and the process is OOM-killed mid-ingestion. Pages are therefore opened
# in bounded batches and each page's cache is released as soon as it is read.
PAGE_BATCH_SIZE = 10


class PdfParser(DocumentParserPort):
    PARSER_NAME = "PdfParser"
    PARSER_VERSION = "1.0.0"

    def parse(self, file_bytes: bytes, file_name: str) -> CanonicalExtractionOutput:
        pages_output = []
        chunks_output = []
        warnings = []
        total_text_length = 0
        chunk_index = 0
        total_tables = 0

        max_pages = settings.MAX_PDF_PAGES
        max_chars = settings.MAX_PDF_TEXT_CHARS
        max_tables = settings.MAX_PDF_TABLES

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            total_pages = len(pdf.pages)

        if total_pages > max_pages:
            warnings.append(
                ExtractionWarningItem(
                    warning_code="RESOURCE_LIMIT_EXCEEDED",
                    warning_message=f"PDF page count ({total_pages}) exceeds safety limit ({max_pages}).",
                    lineage_ref={"format": "pdf", "total_pages": total_pages},
                )
            )

        page_limit = min(total_pages, max_pages)
        stop_reading = False

        for batch_start in range(1, page_limit + 1, PAGE_BATCH_SIZE):
            if stop_reading:
                break

            batch_pages = list(range(batch_start, min(batch_start + PAGE_BATCH_SIZE - 1, page_limit) + 1))
            with pdfplumber.open(BytesIO(file_bytes), pages=batch_pages) as pdf:
                for offset, page in enumerate(pdf.pages):
                    p_idx = batch_pages[offset]
                    try:
                        raw_text = page.extract_text() or ""
                        total_text_length += len(raw_text.strip())

                        pages_output.append(
                            {
                                "page_number": p_idx,
                                "width_px": int(page.width),
                                "height_px": int(page.height),
                                "text_layer_present": len(raw_text.strip()) > 0,
                                "raw_page_text": raw_text,
                            }
                        )

                        if raw_text.strip():
                            chunk_index += 1
                            chunks_output.append(
                                {
                                    "chunk_index": chunk_index,
                                    "chunk_type": "TEXT",
                                    "content": raw_text.strip(),
                                    "source_lineage": {
                                        "format": "pdf",
                                        "page_number": p_idx,
                                        "bbox": [0.0, 0.0, float(page.width), float(page.height)],
                                    },
                                }
                            )

                        if total_text_length > max_chars:
                            warnings.append(
                                ExtractionWarningItem(
                                    warning_code="RESOURCE_LIMIT_EXCEEDED",
                                    warning_message=f"PDF text character count exceeds limit of {max_chars}.",
                                    lineage_ref={"format": "pdf", "page_number": p_idx},
                                )
                            )
                            stop_reading = True
                            break

                        # Extract Candidate Tables
                        tables = page.extract_tables()
                        for t_idx, table in enumerate(tables):
                            if table:
                                total_tables += 1
                                if total_tables > max_tables:
                                    warnings.append(
                                        ExtractionWarningItem(
                                            warning_code="RESOURCE_LIMIT_EXCEEDED",
                                            warning_message=f"PDF table count exceeds limit of {max_tables}.",
                                            lineage_ref={"format": "pdf", "page_number": p_idx},
                                        )
                                    )
                                    break

                                chunk_index += 1
                                table_content = "\n".join([" | ".join([cell or "" for cell in row]) for row in table])
                                chunks_output.append(
                                    {
                                        "chunk_index": chunk_index,
                                        "chunk_type": "TABLE",
                                        "content": table_content,
                                        "source_lineage": {
                                            "format": "pdf",
                                            "page_number": p_idx,
                                            "table_index": t_idx,
                                            "rows_count": len(table),
                                        },
                                    }
                                )
                    finally:
                        # Release the page's parsed objects immediately.
                        page.flush_cache()

            gc.collect()

        # Scanned / Image-Only PDF check
        text_layer_present = total_text_length > 0
        if not text_layer_present:
            status = "AWAITING_REVIEW"
            quality_score = 0.0
            warnings.append(
                ExtractionWarningItem(
                    warning_code="OCR_REQUIRED_BUT_UNAVAILABLE",
                    warning_message="PDF contains no extractable text layer (scanned/image-only). OCR is required but unavailable in Phase 2.",
                    lineage_ref={"format": "pdf", "total_pages": total_pages},
                )
            )
        elif any(w.warning_code == "RESOURCE_LIMIT_EXCEEDED" for w in warnings):
            status = "COMPLETED_WITH_WARNINGS"
            quality_score = 0.70
        elif len(warnings) > 0:
            status = "COMPLETED_WITH_WARNINGS"
            quality_score = 0.85
        else:
            status = "COMPLETED"

            quality_score = 1.0

        return CanonicalExtractionOutput(
            parser_name=self.PARSER_NAME,
            parser_version=self.PARSER_VERSION,
            status=status,
            quality_score=quality_score,
            text_layer_present=text_layer_present,
            pages=pages_output,
            chunks=chunks_output,
            warnings=warnings,
        )
