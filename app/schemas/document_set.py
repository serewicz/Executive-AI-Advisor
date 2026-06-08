from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.document import DocumentClassification, DocumentSourceType, DocumentStatus


class DocumentSetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class DocumentSetCreateResponse(BaseModel):
    document_set_id: UUID
    name: str


class DocumentSetDocumentSummary(BaseModel):
    document_id: UUID
    filename: str
    status: DocumentStatus
    source_type: DocumentSourceType
    classification: DocumentClassification
    uploaded_at: datetime | None = None


class DocumentSetSummary(BaseModel):
    document_set_id: UUID
    name: str
    description: str | None = None
    created_at: datetime | None = None
    document_count: int = 0


class DocumentSetDetail(BaseModel):
    document_set_id: UUID
    name: str
    description: str | None = None
    created_at: datetime | None = None
    documents: list[DocumentSetDocumentSummary]


class DocumentSetListResponse(BaseModel):
    document_sets: list[DocumentSetSummary]


class DocumentSetDocumentResponse(BaseModel):
    document_set_id: UUID
    document_id: UUID


class DocumentSetProcessResponse(BaseModel):
    document_set_id: UUID
    documents_processed: int
    documents: list[DocumentSetDocumentSummary]
