"""Finds where on a PDF page a figure is printed.

A verified fact must be traceable to a physical place in its source, so
candidate evidence carries the bounding box of the number it was read from.
Deterministic table parsing knows the cell rectangle; a figure read out of free
text does not, and evidence written without coordinates is refused at approval.

This locator closes that gap: given the value exactly as it appears in the
document, it finds the words that spell it on the cited page and returns their
union rectangle. It reports nothing rather than guessing — a box that does not
contain the number is worse than no box, because it would send a reviewer to
the wrong part of the page.

Pages are opened one at a time and their caches released, matching the memory
discipline the parser already follows on a 400MB worker.
"""

import io
import re
from typing import Any

import pdfplumber

# A page holding more words than this is pathological (a scanned noise page or
# a generated stress document); locating inside it is not worth the memory.
MAX_WORDS_PER_PAGE = 6000

# How many consecutive words may be joined while trying to match one figure.
# A value such as "5.550.109.551" is occasionally split into a few words by the
# extractor, but never into many.
MAX_WORDS_PER_VALUE = 6


def normalise(text: str) -> str:
    """Strip the formatting noise that separates a printed figure from its text."""
    return re.sub(r"[\s ]", "", text).replace("−", "-")


def _union_bbox(words: list[dict[str, Any]]) -> dict[str, float]:
    return {
        "x0": min(float(w["x0"]) for w in words),
        "y0": min(float(w["top"]) for w in words),
        "x1": max(float(w["x1"]) for w in words),
        "y1": max(float(w["bottom"]) for w in words),
    }


def locate_in_words(words: list[dict[str, Any]], value: str) -> dict[str, float] | None:
    """Union rectangle of the shortest word run that spells `value`.

    Matching is done on normalised text so that a figure printed as
    "5.550.109.551" is still found when the extractor emits it as two words.
    """
    target = normalise(value)
    if not target:
        return None

    for start in range(len(words)):
        joined = ""
        for length in range(MAX_WORDS_PER_VALUE):
            index = start + length
            if index >= len(words):
                break
            joined += normalise(str(words[index].get("text", "")))
            if joined == target:
                return _union_bbox(words[start : index + 1])
            if not target.startswith(joined):
                break
    return None


class PdfValueLocator:
    """Locates figures in one PDF, keeping at most a single page in memory.

    Candidates from a filing arrive grouped by page in practice, so caching the
    most recently used page's words turns a per-candidate page open into one
    open per page.
    """

    def __init__(self, pdf_bytes: bytes) -> None:
        self._pdf_bytes = pdf_bytes
        self._cached_page: int | None = None
        self._cached_words: list[dict[str, Any]] = []

    def _words_for_page(self, page_number: int) -> list[dict[str, Any]]:
        if self._cached_page == page_number:
            return self._cached_words

        words: list[dict[str, Any]] = []
        try:
            with pdfplumber.open(io.BytesIO(self._pdf_bytes)) as pdf:
                if not (1 <= page_number <= len(pdf.pages)):
                    return []
                page = pdf.pages[page_number - 1]
                try:
                    words = page.extract_words() or []
                    if len(words) > MAX_WORDS_PER_PAGE:
                        words = []
                finally:
                    page.flush_cache()
        except Exception:  # noqa: BLE001 - a locator failure must not fail ingestion
            words = []

        self._cached_page = page_number
        self._cached_words = words
        return words

    def locate(self, page_number: int | None, value: str) -> dict[str, float] | None:
        """Bounding box of `value` on `page_number`, or None if it is not found."""
        if not page_number or not value:
            return None
        return locate_in_words(self._words_for_page(int(page_number)), value)
