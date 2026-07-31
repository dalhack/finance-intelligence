import csv
import io

import chardet

from services.api.app.core.config import settings
from services.api.app.parsers.base import (
    CanonicalExtractionOutput,
    DocumentParserPort,
    ExtractionWarningItem,
)

ALLOWED_ENCODINGS = {"utf-8", "utf-8-sig", "ascii", "iso-8859-1", "windows-1254", "latin-1", "utf-16"}
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class CsvParser(DocumentParserPort):
    PARSER_NAME = "CsvParser"
    PARSER_VERSION = "1.0.0"

    def parse(self, file_bytes: bytes, file_name: str) -> CanonicalExtractionOutput:
        # Null-byte rejection
        if b"\x00" in file_bytes:
            return CanonicalExtractionOutput(
                parser_name=self.PARSER_NAME,
                parser_version=self.PARSER_VERSION,
                status="REJECTED",
                quality_score=0.0,
                text_layer_present=False,
                pages=[],
                chunks=[],
                warnings=[
                    ExtractionWarningItem(
                        warning_code="NULL_BYTE_DETECTED",
                        warning_message="Binary payload contains null bytes; invalid CSV text file.",
                        lineage_ref={"format": "csv"},
                    )
                ],
            )

        # Strict Decoding Pipeline (No errors="replace")
        text_content = None

        if file_bytes.startswith(b"\xef\xbb\xbf"):
            try:
                text_content = file_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                pass

        if text_content is None:
            try:
                text_content = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                res = chardet.detect(file_bytes[:65536])
                cand = (res.get("encoding") or "").lower()
                conf = res.get("confidence", 0.0) or 0.0
                if cand in ALLOWED_ENCODINGS and conf >= 0.7:
                    try:
                        text_content = file_bytes.decode(cand)
                    except (UnicodeDecodeError, LookupError):
                        pass

        if text_content is None:
            return CanonicalExtractionOutput(
                parser_name=self.PARSER_NAME,
                parser_version=self.PARSER_VERSION,
                status="AWAITING_REVIEW",
                quality_score=0.0,
                text_layer_present=False,
                pages=[],
                chunks=[],
                warnings=[
                    ExtractionWarningItem(
                        warning_code="ENCODING_UNCERTAIN",
                        warning_message="Strict CSV text decoding failed. File requires manual review.",
                        lineage_ref={"format": "csv"},
                    )
                ],
            )

        # Delimiter Sniffing
        sample_str = text_content[:4096]
        delimiter = ","
        try:
            dialect = csv.Sniffer().sniff(sample_str, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            pass

        reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
        chunks_output = []
        warnings = []
        headers: list[str] = []

        chunk_index = 0
        total_extracted_chars = 0
        line_number = 0

        max_rows = settings.MAX_CSV_ROWS
        max_cols = settings.MAX_CSV_COLS
        max_cell_len = settings.MAX_CELL_LEN
        max_chars = settings.MAX_EXTRACTED_CHARS

        for row in reader:
            line_number += 1
            if line_number > max_rows:
                warnings.append(
                    ExtractionWarningItem(
                        warning_code="RESOURCE_LIMIT_EXCEEDED",
                        warning_message=f"CSV row count exceeds limit of {max_rows}.",
                        lineage_ref={"format": "csv", "line_number": line_number},
                    )
                )
                break

            if len(row) > max_cols:
                warnings.append(
                    ExtractionWarningItem(
                        warning_code="RESOURCE_LIMIT_EXCEEDED",
                        warning_message=f"CSV column count ({len(row)}) exceeds limit of {max_cols}.",
                        lineage_ref={"format": "csv", "line_number": line_number},
                    )
                )
                break

            if line_number == 1 and not headers:
                headers = row
                chunk_index += 1
                header_str = delimiter.join(row)
                total_extracted_chars += len(header_str)
                chunks_output.append(
                    {
                        "chunk_index": chunk_index,
                        "chunk_type": "HEADER",
                        "content": header_str,
                        "source_lineage": {"format": "csv", "line_number": line_number, "is_header": True},
                    }
                )
                continue

            for col_idx, cell_val in enumerate(row):
                raw_value = cell_val
                cell_truncated = False
                if len(raw_value) > max_cell_len:
                    raw_value = raw_value[:max_cell_len]
                    cell_truncated = True
                    warnings.append(
                        ExtractionWarningItem(
                            warning_code="CSV_CELL_TRUNCATED",
                            warning_message=f"CSV cell length in line {line_number}, col {col_idx + 1} exceeds limit of {max_cell_len} and was truncated.",
                            lineage_ref={
                                "format": "csv",
                                "line_number": line_number,
                                "column_index": col_idx + 1,
                                "truncated": True,
                            },
                        )
                    )

                has_risk = any(raw_value.startswith(prefix) for prefix in FORMULA_PREFIXES)
                leading_char = raw_value[0] if (has_risk and len(raw_value) > 0) else None

                if has_risk:
                    warnings.append(
                        ExtractionWarningItem(
                            warning_code="CSV_FORMULA_INJECTION_RISK",
                            warning_message=f"Formula injection risk in line {line_number}, col {col_idx + 1}: leading '{leading_char}'",
                            lineage_ref={
                                "format": "csv",
                                "line_number": line_number,
                                "column_index": col_idx + 1,
                                "leading_char": leading_char,
                            },
                        )
                    )

                header_name = headers[col_idx] if col_idx < len(headers) else f"Column_{col_idx + 1}"

                chunk_index += 1
                total_extracted_chars += len(raw_value)

                # NO export_safe_value IN LINEAGE OR DATABASE!
                chunks_output.append(
                    {
                        "chunk_index": chunk_index,
                        "chunk_type": "CELL",
                        "content": raw_value,  # RAW VALUE PRESERVED WITHOUT MUTATION
                        "source_lineage": {
                            "format": "csv",
                            "line_number": line_number,
                            "row_index": line_number - 1,
                            "column_index": col_idx + 1,
                            "column_name": header_name,
                            "truncated": cell_truncated,
                            "formula_injection_risk": has_risk,
                            "leading_formula_character": leading_char,
                        },
                    }
                )

                if total_extracted_chars > max_chars:
                    warnings.append(
                        ExtractionWarningItem(
                            warning_code="RESOURCE_LIMIT_EXCEEDED",
                            warning_message=f"Extracted character limit ({max_chars}) reached.",
                            lineage_ref={"format": "csv"},
                        )
                    )
                    break

        status = "COMPLETED_WITH_WARNINGS" if warnings else "COMPLETED"

        quality_score = 0.90 if warnings else 1.0

        return CanonicalExtractionOutput(
            parser_name=self.PARSER_NAME,
            parser_version=self.PARSER_VERSION,
            status=status,
            quality_score=quality_score,
            text_layer_present=True,
            pages=[],
            chunks=chunks_output,
            warnings=warnings,
        )
