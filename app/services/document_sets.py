"""Read operations on document sets (investigations).

These functions are the public contract used by both the REST routes and the
MCP server. Adapters must not import from ``app.api.routes``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentSet, DocumentSetDocument
from app.schemas.document_set import (
    DocumentSetDetail,
    DocumentSetDocumentSummary,
    DocumentSetListResponse,
    DocumentSetSummary,
)


def list_document_sets(db: Session) -> DocumentSetListResponse:
    rows = db.execute(
        select(DocumentSet, func.count(DocumentSetDocument.document_id))
        .outerjoin(DocumentSetDocument, DocumentSetDocument.document_set_id == DocumentSet.id)
        .group_by(DocumentSet.id)
        .order_by(DocumentSet.created_at.desc())
    ).all()
    return DocumentSetListResponse(
        document_sets=[
            DocumentSetSummary(
                document_set_id=document_set.id,
                name=document_set.name,
                description=document_set.description,
                created_at=document_set.created_at,
                document_count=document_count,
            )
            for document_set, document_count in rows
        ]
    )


def get_document_set(document_set_id: UUID, db: Session) -> DocumentSet | None:
    return db.get(DocumentSet, document_set_id)


def document_set_detail(document_set: DocumentSet, db: Session) -> DocumentSetDetail:
    return DocumentSetDetail(
        document_set_id=document_set.id,
        name=document_set.name,
        description=document_set.description,
        created_at=document_set.created_at,
        documents=[document_summary(document) for document in documents_for_set(document_set.id, db)],
    )


def documents_for_set(document_set_id: UUID, db: Session) -> list[Document]:
    return list(
        db.scalars(
            select(Document)
            .join(DocumentSetDocument, DocumentSetDocument.document_id == Document.id)
            .where(DocumentSetDocument.document_set_id == document_set_id)
            .order_by(Document.uploaded_at.desc())
        ).all()
    )


def document_summary(document: Document) -> DocumentSetDocumentSummary:
    return DocumentSetDocumentSummary(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        source_type=document.source_type,
        classification=document.classification,
        uploaded_at=document.uploaded_at,
    )
