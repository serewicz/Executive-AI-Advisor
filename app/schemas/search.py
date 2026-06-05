from uuid import UUID

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.document import DocumentClassification, DocumentSourceType


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=settings.max_search_query_chars)
    top_k: int = Field(default=5, ge=1, le=20)
    source_type: DocumentSourceType | None = None
    classification: DocumentClassification | None = None


class SearchResult(BaseModel):
    document_id: UUID
    document_title: str
    chunk_id: UUID
    chunk_index: int
    page_start: int
    page_end: int
    similarity_score: float
    source_type: DocumentSourceType
    classification: DocumentClassification
    content_preview: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
