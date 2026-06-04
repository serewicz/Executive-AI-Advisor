from typing import Literal
from uuid import UUID

from pydantic import BaseModel


DocumentStatus = Literal["uploaded", "parsing", "parsed", "chunked", "embedded", "indexed", "failed"]
DocumentClassification = Literal["public", "internal", "confidential", "restricted"]
DocumentSourceType = Literal[
    "sec_filing",
    "diligence_report",
    "technology_assessment",
    "board_material",
]


class DocumentUploadRequest(BaseModel):
    source_type: DocumentSourceType = "technology_assessment"
    classification: DocumentClassification = "internal"


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    filename: str
    status: DocumentStatus
    source_type: DocumentSourceType
    classification: DocumentClassification


class DocumentParseResponse(BaseModel):
    document_id: UUID
    status: DocumentStatus
    pages_parsed: int


class DocumentPagePreview(BaseModel):
    page_number: int
    text_preview: str


class DocumentPagesResponse(BaseModel):
    document_id: UUID
    pages: list[DocumentPagePreview]
