import hashlib
import os
import re
import zipfile
from io import BytesIO
from typing import Any

import chardet
import filetype
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from services.api.app.core.errors import BaseAPIException

MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_XLSX_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB
MAX_CSV_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB

MAX_ZIP_RATIO = 100
MAX_ZIP_ENTRIES = 500
MAX_TOTAL_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES = 20 * 1024 * 1024  # 20 MB

ALLOWED_PDF_MIMES = {"application/pdf"}
ALLOWED_XLSX_MIMES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/octet-stream",
}
ALLOWED_CSV_MIMES = {
    "text/csv",
    "text/plain",
    "application/csv",
    "text/comma-separated-values",
    "application/octet-stream",
}


class SecurityPipelineException(BaseAPIException):
    def __init__(self, code: str, message: str, status_code: int = 400, details: Any = None):
        super().__init__(status_code=status_code, code=code, message=message, details=details)


def sanitize_filename(filename: str) -> str:
    cleaned = os.path.basename(filename)
    sanitized = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", cleaned)
    return sanitized or "unnamed_document"


def validate_file_security(
    file_bytes: bytes,
    declared_filename: str,
    declared_mime: str,
) -> dict[str, Any]:
    sanitized_name = sanitize_filename(declared_filename)
    name_parts = sanitized_name.lower().split(".")

    # Double extension check
    if len(name_parts) > 2:
        forbidden_sub_exts = {"exe", "sh", "bat", "cmd", "vbs", "js", "py", "php", "pl"}
        if any(part in forbidden_sub_exts for part in name_parts[:-1]):
            raise SecurityPipelineException(
                code="UNSUPPORTED_FILE_TYPE",
                message=f"Double extension attack vector detected in filename '{declared_filename}'.",
                status_code=415,
            )

    _, ext = os.path.splitext(sanitized_name.lower())

    if ext not in [".pdf", ".xlsx", ".csv"]:
        raise SecurityPipelineException(
            code="UNSUPPORTED_FILE_TYPE",
            message=f"Extension '{ext}' is not supported. Supported extensions: .pdf, .xlsx, .csv",
            status_code=415,
        )

    # 1. Size Limits
    file_size = len(file_bytes)
    max_allowed = MAX_PDF_SIZE_BYTES if ext == ".pdf" else MAX_XLSX_SIZE_BYTES
    if file_size > max_allowed:
        raise SecurityPipelineException(
            code="FILE_TOO_LARGE",
            message=f"File size {file_size} bytes exceeds maximum limit of {max_allowed} bytes.",
            status_code=413,
        )

    # 2. SHA-256 Calculation
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # 3. Magic Bytes & Signature Inspection
    detected_type = filetype.guess(file_bytes[:4096])
    detected_mime = detected_type.mime if detected_type else None
    decl_mime_clean = declared_mime.lower().strip()

    # 4. MIME Reconciliation Matrix
    if ext == ".pdf":
        if decl_mime_clean not in ALLOWED_PDF_MIMES and decl_mime_clean != "application/octet-stream":
            raise SecurityPipelineException(
                code="MIME_MISMATCH",
                message=f"Declared MIME '{declared_mime}' does not match expected PDF MIME application/pdf.",
                status_code=415,
            )

        if not file_bytes.startswith(b"%PDF-"):
            raise SecurityPipelineException(
                code="MIME_MISMATCH",
                message="File header does not match valid PDF signature %PDF-.",
                status_code=415,
            )

        detected_mime = "application/pdf"
        try:
            reader = PdfReader(BytesIO(file_bytes))
            if reader.is_encrypted:
                raise SecurityPipelineException(
                    code="ENCRYPTED_DOCUMENT",
                    message="Password-protected or encrypted PDFs are not supported.",
                    status_code=422,
                )
        except PyPdfError as err:
            raise SecurityPipelineException(
                code="MALFORMED_DOCUMENT",
                message=f"PDF structure is corrupt or unreadable: {err!s}",
                status_code=422,
            )

    elif ext == ".xlsx":
        if decl_mime_clean not in ALLOWED_XLSX_MIMES:
            raise SecurityPipelineException(
                code="MIME_MISMATCH",
                message=f"Declared MIME '{declared_mime}' does not match expected XLSX OOXML MIME.",
                status_code=415,
            )

        if not (detected_mime == "application/zip" or file_bytes.startswith(b"PK\x03\x04")):
            raise SecurityPipelineException(
                code="MIME_MISMATCH",
                message="File signature does not match valid XLSX OOXML ZIP container.",
                status_code=415,
            )

        detected_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        try:
            with zipfile.ZipFile(BytesIO(file_bytes), "r") as zf:
                entries = zf.infolist()
                if len(entries) > MAX_ZIP_ENTRIES:
                    raise SecurityPipelineException(
                        code="RESOURCE_LIMIT_EXCEEDED",
                        message=f"XLSX ZIP entry count ({len(entries)}) exceeds safety limit ({MAX_ZIP_ENTRIES}).",
                        status_code=422,
                    )

                entry_names = [e.filename for e in entries]
                # MUST contain BOTH [Content_Types].xml AND xl/workbook.xml (AND condition)
                if not ("[Content_Types].xml" in entry_names and "xl/workbook.xml" in entry_names):
                    raise SecurityPipelineException(
                        code="MALFORMED_DOCUMENT",
                        message="XLSX container is missing required OOXML [Content_Types].xml or xl/workbook.xml structure.",
                        status_code=422,
                    )

                total_uncompressed = 0
                for entry in entries:
                    total_uncompressed += entry.file_size
                    if entry.file_size > MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES:
                        raise SecurityPipelineException(
                            code="RESOURCE_LIMIT_EXCEEDED",
                            message=f"ZIP entry '{entry.filename}' uncompressed size exceeds limit.",
                            status_code=422,
                        )

                    # Path Traversal Checks
                    name = entry.filename
                    if ".." in name or name.startswith("/") or "\\" in name or ":" in name or "\x00" in name:
                        raise SecurityPipelineException(
                            code="PATH_TRAVERSAL_DETECTED",
                            message=f"ZIP entry path traversal detected: {entry.filename}",
                            status_code=400,
                        )

                    if entry.compress_size > 0:
                        ratio = entry.file_size / entry.compress_size
                        if ratio > MAX_ZIP_RATIO:
                            raise SecurityPipelineException(
                                code="RESOURCE_LIMIT_EXCEEDED",
                                message=f"Zip bomb risk: Compression ratio {ratio:.1f} exceeds limit {MAX_ZIP_RATIO}.",
                                status_code=422,
                            )

                if total_uncompressed > MAX_TOTAL_UNCOMPRESSED_BYTES:
                    raise SecurityPipelineException(
                        code="RESOURCE_LIMIT_EXCEEDED",
                        message="XLSX total uncompressed size exceeds limit.",
                        status_code=422,
                    )

        except zipfile.BadZipFile:
            raise SecurityPipelineException(
                code="MALFORMED_DOCUMENT",
                message="XLSX file is corrupted or not a valid ZIP container.",
                status_code=422,
            )

    elif ext == ".csv":
        if decl_mime_clean not in ALLOWED_CSV_MIMES:
            raise SecurityPipelineException(
                code="MIME_MISMATCH",
                message=f"Declared MIME '{declared_mime}' is not permitted for CSV text documents.",
                status_code=415,
            )

        if b"\x00" in file_bytes[:4096]:
            raise SecurityPipelineException(
                code="MIME_MISMATCH",
                message="CSV payload contains null bytes; binary payload rejected for CSV text document.",
                status_code=415,
            )

        detected_mime = "text/csv"
        sample = file_bytes[:65536]
        res = chardet.detect(sample)
        confidence = res.get("confidence", 0.0) or 0.0

        if confidence < 0.7:
            try:
                sample.decode("utf-8")
            except UnicodeDecodeError:
                raise SecurityPipelineException(
                    code="ENCODING_UNCERTAIN",
                    message="CSV text encoding is ambiguous or unreadable. Strict UTF-8 decode failed.",
                    status_code=422,
                )

    return {
        "sanitized_filename": sanitized_name,
        "extension": ext,
        "file_size_bytes": file_size,
        "sha256_hash": sha256_hash,
        "declared_mime": declared_mime,
        "detected_mime": detected_mime,
    }
