import re
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID


class PDFParsingError(RuntimeError):
    pass


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    metadata: dict = field(default_factory=dict)


def parse_pdf(document_id: UUID, file_path: str) -> list[ParsedPage]:
    path = Path(file_path)
    if not path.exists():
        raise PDFParsingError(f"PDF file does not exist: {file_path}")

    try:
        pages = _parse_with_docling(path)
    except Exception as docling_error:
        try:
            pages = _parse_with_pypdf(path)
        except Exception as pypdf_error:
            raise PDFParsingError(
                f"Failed to parse document {document_id}: {docling_error}; fallback failed: {pypdf_error}"
            ) from pypdf_error

    return [page for page in pages if page.text]


def _parse_with_docling(path: Path) -> list[ParsedPage]:
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(path)
    document = result.document
    pages = getattr(document, "pages", {}) or {}
    parsed_pages: list[ParsedPage] = []

    for page_number in sorted(pages):
        text = _normalize_whitespace(document.export_to_markdown(page_no=page_number))
        if text:
            parsed_pages.append(
                ParsedPage(
                    page_number=page_number,
                    text=text,
                    metadata={"parser": "docling"},
                )
            )

    if parsed_pages:
        return parsed_pages

    text = _normalize_whitespace(document.export_to_markdown())
    return [ParsedPage(page_number=1, text=text, metadata={"parser": "docling"})] if text else []


def _parse_with_pypdf(path: Path) -> list[ParsedPage]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parsed_pages: list[ParsedPage] = []

    for index, page in enumerate(reader.pages, start=1):
        text = _normalize_whitespace(page.extract_text() or "")
        if text:
            parsed_pages.append(
                ParsedPage(
                    page_number=index,
                    text=text,
                    metadata={"parser": "pypdf"},
                )
            )

    return parsed_pages


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
