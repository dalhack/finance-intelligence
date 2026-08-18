"""The locator must point at the figure itself, or admit it cannot."""

import io

import pdfplumber
import pytest
from app.parsers.value_locator import PdfValueLocator, locate_in_words, normalise

PAGE_WIDTH = 595
PAGE_HEIGHT = 842


def _pdf_with(lines: list[tuple[float, float, str]]) -> bytes:
    """A one-page PDF drawing each text at its position, built without a writer.

    The suite has no PDF generator dependency, and adding one to place a few
    strings on a page would be a heavier commitment than writing the file.
    """
    drawing = "".join(f"BT /F1 11 Tf {x} {y} Td ({text}) Tj ET\n" for x, y, text in lines)
    stream = drawing.encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            f"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("latin-1"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n").encode()
    return bytes(out)


def _words(text: str) -> list[dict[str, float | str]]:
    """Word dicts shaped like pdfplumber's, laid out left to right."""
    out: list[dict[str, float | str]] = []
    x = 0.0
    for token in text.split():
        out.append({"text": token, "x0": x, "x1": x + 10.0, "top": 100.0, "bottom": 112.0})
        x += 12.0
    return out


def test_finds_a_single_word_figure():
    words = _words("VARLIKLAR TOPLAMI 5.550.109.551")
    bbox = locate_in_words(words, "5.550.109.551")
    assert bbox == {"x0": 24.0, "y0": 100.0, "x1": 34.0, "y1": 112.0}


def test_joins_a_figure_split_across_words():
    """Extractors sometimes break a grouped number apart; the box must cover all of it."""
    words = _words("Toplam 5.550. 109.551 TL")
    bbox = locate_in_words(words, "5.550.109.551")
    assert bbox is not None
    assert bbox["x0"] == 12.0
    assert bbox["x1"] == 34.0


def test_reports_nothing_when_the_figure_is_absent():
    """A wrong box would send the reviewer to the wrong place — None is required."""
    assert locate_in_words(_words("VARLIKLAR TOPLAMI 5.550.109.551"), "9.999.999") is None


def test_does_not_match_a_longer_number_containing_the_value():
    assert locate_in_words(_words("Toplam 15.550.109.551"), "5.550.109.551") is None


def test_normalise_ignores_spacing_but_keeps_digits():
    assert normalise("5 550 109") == "5550109"
    assert normalise("−12") == "-12"


def test_locates_on_the_real_page_of_a_pdf():
    pdf = _pdf_with([(72, 700, "VARLIKLAR TOPLAMI"), (350, 700, "5.550.109.551")])
    locator = PdfValueLocator(pdf)

    bbox = locator.locate(1, "5.550.109.551")

    assert bbox is not None
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        page_width = doc.pages[0].width
    # The figure sits in the right half of the page, where it was drawn.
    assert bbox["x0"] > page_width / 2
    assert bbox["x1"] > bbox["x0"]
    assert bbox["y1"] > bbox["y0"]


def test_absent_page_and_empty_value_are_refused():
    locator = PdfValueLocator(_pdf_with([(72, 700, "TOPLAM 1.234")]))
    assert locator.locate(99, "1.234") is None
    assert locator.locate(None, "1.234") is None
    assert locator.locate(1, "") is None


def test_corrupt_bytes_do_not_raise():
    """A locator failure must never fail an ingestion job."""
    assert PdfValueLocator(b"not a pdf").locate(1, "1.234") is None


@pytest.mark.parametrize("value", ["1.234", "(1.234)", "-1.234"])
def test_signed_and_bracketed_figures_are_located(value):
    locator = PdfValueLocator(_pdf_with([(72, 700, f"Kalem {value}")]))
    assert locator.locate(1, value) is not None
