from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ExtractionWarningItem(BaseModel):
    warning_code: str
    warning_message: str
    lineage_ref: dict[str, Any] = Field(default_factory=dict)


class CanonicalExtractionOutput(BaseModel):
    parser_name: str
    parser_version: str
    status: str  # EXTRACTED, COMPLETED_WITH_WARNINGS, AWAITING_REVIEW, FAILED
    quality_score: float = 1.0
    text_layer_present: bool = True
    pages: list[dict[str, Any]] = Field(default_factory=list)
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[ExtractionWarningItem] = Field(default_factory=list)


class DocumentParserPort(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes, file_name: str) -> CanonicalExtractionOutput:
        """Parses physical binary content into a canonical extraction output."""
