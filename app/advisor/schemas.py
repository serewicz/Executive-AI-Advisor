from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.document import DocumentClassification, DocumentSourceType


Confidence = Literal["high", "medium", "low"]


class AdvisorAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=settings.max_search_query_chars)
    top_k: int = Field(default=5, ge=1, le=20)
    source_type: DocumentSourceType | None = None
    classification: DocumentClassification | None = None


class AdvisorCitation(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: UUID
    page_start: int
    page_end: int
    excerpt: str


class AdvisorAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[AdvisorCitation]
    confidence: Confidence
    limitations: list[str]
