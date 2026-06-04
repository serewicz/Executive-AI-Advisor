from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.ingestion.parser import PDFParsingError, parse_pdf
from app.models.document import Document, ParsedDocumentPage


class DocumentNotFoundError(LookupError):
    pass


class InvalidDocumentStatusError(ValueError):
    pass


def parse_uploaded_document(document_id: UUID, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document not found: {document_id}")

    if document.status not in {"uploaded", "failed"}:
        raise InvalidDocumentStatusError(
            f"Document {document_id} cannot be parsed from status {document.status}."
        )

    document.status = "parsing"
    db.commit()

    try:
        parsed_pages = parse_pdf(document.id, document.file_path)
        db.execute(delete(ParsedDocumentPage).where(ParsedDocumentPage.document_id == document.id))
        db.add_all(
            [
                ParsedDocumentPage(
                    document_id=document.id,
                    page_number=page.page_number,
                    text=page.text,
                    page_metadata=page.metadata,
                )
                for page in parsed_pages
            ]
        )
        document.status = "parsed"
        document.document_metadata = {
            **(document.document_metadata or {}),
            "pages_parsed": len(parsed_pages),
        }
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        document.status = "failed"
        document.document_metadata = {
            **(document.document_metadata or {}),
            "parse_error": str(exc),
        }
        db.commit()
        raise PDFParsingError(f"Failed to parse document {document_id}: {exc}") from exc
