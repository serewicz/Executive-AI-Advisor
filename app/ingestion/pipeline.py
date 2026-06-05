from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ingestion.chunker import chunk_document_pages
from app.ingestion.embedder import EmbeddingError, embed_texts
from app.ingestion.parser import PDFParsingError, parse_pdf
from app.models.document import Document, DocumentChunk, ParsedDocumentPage


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
        if not parsed_pages:
            raise PDFParsingError("No text pages were parsed from the PDF.")

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
        db.rollback()
        document.status = "failed"
        document.document_metadata = {
            **(document.document_metadata or {}),
            "parse_error": str(exc),
        }
        db.commit()
        raise PDFParsingError(f"Failed to parse document {document_id}: {exc}") from exc


def chunk_parsed_document(document_id: UUID, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document not found: {document_id}")

    if document.status not in {"parsed", "chunked"}:
        raise InvalidDocumentStatusError(
            f"Document {document_id} cannot be chunked from status {document.status}."
        )

    try:
        pages = db.scalars(
            select(ParsedDocumentPage)
            .where(ParsedDocumentPage.document_id == document.id)
            .order_by(ParsedDocumentPage.page_number)
        ).all()
        chunks = chunk_document_pages(pages)
        if not chunks:
            raise ValueError("No chunks were generated from parsed document pages.")

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.add_all(
            [
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                    token_count=chunk.token_count,
                    chunk_metadata=chunk.metadata,
                )
                for chunk in chunks
            ]
        )
        document.status = "chunked"
        document.document_metadata = {
            **(document.document_metadata or {}),
            "chunks_created": len(chunks),
        }
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        document.status = "failed"
        document.document_metadata = {
            **(document.document_metadata or {}),
            "chunk_error": str(exc),
        }
        db.commit()
        raise RuntimeError(f"Failed to chunk document {document_id}: {exc}") from exc


def embed_document_chunks(document_id: UUID, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise DocumentNotFoundError(f"Document not found: {document_id}")

    if document.status not in {"chunked", "embedded"}:
        raise InvalidDocumentStatusError(
            f"Document {document_id} cannot be embedded from status {document.status}."
        )

    try:
        chunks = db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.chunk_index)
        ).all()
        chunks_without_embeddings = [chunk for chunk in chunks if chunk.embedding is None]

        if chunks_without_embeddings:
            embeddings = embed_texts([chunk.content for chunk in chunks_without_embeddings])
            for chunk, embedding in zip(chunks_without_embeddings, embeddings, strict=True):
                chunk.embedding = embedding

        document.status = "embedded"
        document.document_metadata = {
            **(document.document_metadata or {}),
            "chunks_embedded": len(chunks_without_embeddings),
        }
        db.commit()
        db.refresh(document)
        return document
    except Exception as exc:
        db.rollback()
        document.status = "failed"
        document.document_metadata = {
            **(document.document_metadata or {}),
            "embedding_error": str(exc),
        }
        db.commit()
        raise EmbeddingError(f"Failed to embed document {document_id}: {exc}") from exc
