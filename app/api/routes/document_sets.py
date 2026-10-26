from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.dependencies import get_db
from app.ingestion.pipeline import (
    chunk_parsed_document,
    embed_document_chunks,
    parse_uploaded_document,
)
from app.models.document import Document, DocumentSet, DocumentSetDocument
from app.services import document_sets as document_set_service
from app.schemas.document_set import (
    DocumentSetCreateRequest,
    DocumentSetCreateResponse,
    DocumentSetDetail,
    DocumentSetDocumentResponse,
    DocumentSetListResponse,
    DocumentSetProcessResponse,
)


router = APIRouter(prefix="/document-sets", tags=["document sets"])


@router.post("", response_model=DocumentSetCreateResponse, status_code=status.HTTP_201_CREATED)
def create_document_set(request: DocumentSetCreateRequest, db: Session = Depends(get_db)) -> DocumentSetCreateResponse:
    document_set = DocumentSet(name=request.name, description=request.description)
    db.add(document_set)
    db.commit()
    db.refresh(document_set)

    return DocumentSetCreateResponse(document_set_id=document_set.id, name=document_set.name)


@router.get("", response_model=DocumentSetListResponse)
def list_document_sets(db: Session = Depends(get_db)) -> DocumentSetListResponse:
    return document_set_service.list_document_sets(db)


@router.get("/{document_set_id}", response_model=DocumentSetDetail)
def get_document_set(document_set_id: UUID, db: Session = Depends(get_db)) -> DocumentSetDetail:
    document_set = _get_document_set_or_404(document_set_id, db)
    return document_set_service.document_set_detail(document_set, db)


@router.post(
    "/{document_set_id}/documents/{document_id}",
    response_model=DocumentSetDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_document_to_set(
    document_set_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
) -> DocumentSetDocumentResponse:
    _get_document_set_or_404(document_set_id, db)
    _get_document_or_404(document_id, db)

    existing = db.get(DocumentSetDocument, {"document_set_id": document_set_id, "document_id": document_id})
    if existing is None:
        db.add(DocumentSetDocument(document_set_id=document_set_id, document_id=document_id))
        db.commit()

    return DocumentSetDocumentResponse(document_set_id=document_set_id, document_id=document_id)


@router.delete(
    "/{document_set_id}/documents/{document_id}",
    response_model=DocumentSetDocumentResponse,
)
def remove_document_from_set(
    document_set_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
) -> DocumentSetDocumentResponse:
    _get_document_set_or_404(document_set_id, db)
    _get_document_or_404(document_id, db)
    db.execute(
        delete(DocumentSetDocument).where(
            DocumentSetDocument.document_set_id == document_set_id,
            DocumentSetDocument.document_id == document_id,
        )
    )
    db.commit()
    return DocumentSetDocumentResponse(document_set_id=document_set_id, document_id=document_id)


@router.post("/{document_set_id}/process", response_model=DocumentSetProcessResponse)
def process_document_set(document_set_id: UUID, db: Session = Depends(get_db)) -> DocumentSetProcessResponse:
    document_set = _get_document_set_or_404(document_set_id, db)
    documents = document_set_service.documents_for_set(document_set.id, db)

    processed = 0
    for document in documents:
        original_status = document.status
        if document.status in {"uploaded", "failed"}:
            document = parse_uploaded_document(document.id, db)
        if document.status == "parsed":
            document = chunk_parsed_document(document.id, db)
        if document.status == "chunked":
            embed_document_chunks(document.id, db)
        if original_status != "embedded":
            processed += 1

    updated_documents = document_set_service.documents_for_set(document_set.id, db)
    return DocumentSetProcessResponse(
        document_set_id=document_set.id,
        documents_processed=processed,
        documents=[document_set_service.document_summary(document) for document in updated_documents],
    )


def attach_document_to_set(document_set_id: UUID, document_id: UUID, db: Session) -> None:
    if db.get(DocumentSet, document_set_id) is None:
        raise LookupError(f"Document set not found: {document_set_id}")
    if db.get(DocumentSetDocument, {"document_set_id": document_set_id, "document_id": document_id}) is None:
        db.add(DocumentSetDocument(document_set_id=document_set_id, document_id=document_id))


def _get_document_set_or_404(document_set_id: UUID, db: Session) -> DocumentSet:
    document_set = db.get(DocumentSet, document_set_id)
    if document_set is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document set not found.")
    return document_set


def _get_document_or_404(document_id: UUID, db: Session) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document
