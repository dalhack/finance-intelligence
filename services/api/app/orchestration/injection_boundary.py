class PromptInjectionBoundary:
    """Isolates untrusted user/document snippets into explicit structural tags."""

    @staticmethod
    def wrap_untrusted_content(raw_content: str) -> str:
        # Sanitize any malicious attempt to close the tag prematurely
        sanitized = raw_content.replace("</untrusted_document_content>", "[TAG_CLOSED_ATTEMPT]")
        return f"<untrusted_document_content>\n{sanitized}\n</untrusted_document_content>"
