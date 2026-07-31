from services.api.app.core.errors import BaseAPIException
from services.api.app.parsers.base import DocumentParserPort
from services.api.app.parsers.csv_parser import CsvParser
from services.api.app.parsers.pdf_parser import PdfParser
from services.api.app.parsers.xlsx_parser import XlsxParser


class ParserNotFoundException(BaseAPIException):
    def __init__(self, detected_mime: str):
        super().__init__(
            status_code=415,
            code="UNSUPPORTED_FILE_TYPE",
            message=f"No parser registered for detected MIME type: {detected_mime}",
        )


class ParserRegistry:
    def __init__(self):
        self._parsers: dict[str, DocumentParserPort] = {
            "application/pdf": PdfParser(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": XlsxParser(),
            "text/csv": CsvParser(),
        }

    def get_parser(self, detected_mime: str) -> DocumentParserPort:
        parser = self._parsers.get(detected_mime)
        if not parser:
            raise ParserNotFoundException(detected_mime)
        return parser


parser_registry = ParserRegistry()
