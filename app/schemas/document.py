from typing import Literal
from uuid import UUID

from pydantic import BaseModel


DocumentStatus = Literal["uploaded", "parsed", "chunked", "embedded", "indexed", "failed"]
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
    status: DocumentStatus
