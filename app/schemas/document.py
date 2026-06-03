from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


DocumentStatus = Literal["uploaded", "parsed", "chunked", "embedded", "failed"]
DocumentClassification = Literal["public", "internal", "confidential", "restricted"]
DocumentSourceType = Literal[
    "sec_filing",
    "diligence_report",
    "technology_assessment",
    "board_material",
]


class DocumentUploadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    source: str | None = Field(default=None, max_length=512)
    source_type: DocumentSourceType = "technology_assessment"
    classification: DocumentClassification = "internal"
    document_metadata: dict = Field(default_factory=dict)


class DocumentUploadResponse(BaseModel):
    id: UUID
    title: str
    source_type: DocumentSourceType
    classification: DocumentClassification
    status: DocumentStatus
