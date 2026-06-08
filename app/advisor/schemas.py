from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.config import settings
from app.schemas.document import DocumentClassification, DocumentSourceType


Confidence = Literal["high", "medium", "low"]
SummaryType = Literal[
    "technology_risk",
    "diligence_summary",
    "ai_readiness",
    "security_governance",
    "board_brief",
]


class AdvisorAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=settings.max_search_query_chars)
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: UUID | None = None
    document_set_id: UUID | None = None
    source_type: DocumentSourceType | None = None
    classification: DocumentClassification | None = None


class AdvisorCitation(BaseModel):
    source_label: str
    document_id: UUID
    document_title: str
    chunk_id: UUID
    page_start: int
    page_end: int
    excerpt: str
    relevance_reason: str | None = None
    full_source_text: str | None = None


class AdvisorAskResponse(BaseModel):
    question: str
    answer: str
    citations: list[AdvisorCitation]
    confidence: Confidence
    limitations: list[str]
    scope: Literal["document", "document_set", "global"] = "global"
    document_id: UUID | None = None
    document_set_id: UUID | None = None


class Citation(BaseModel):
    source_label: str
    document_id: UUID
    document_title: str
    chunk_id: UUID
    page_start: int
    page_end: int
    excerpt: str
    relevance_reason: str | None = None
    full_source_text: str | None = None


class BoardMemo(BaseModel):
    executive_summary: str
    key_risks: list[str]
    evidence: list[str]
    board_questions: list[str]
    recommended_actions: list[str]
    limitations: list[str]


class BoardSummaryRequest(BaseModel):
    document_id: UUID | None = None
    document_set_id: UUID | None = None
    summary_type: SummaryType
    top_k: int = Field(default=12, ge=3, le=25)

    @model_validator(mode="after")
    def require_document_or_set(self):
        if self.document_id is None and self.document_set_id is None:
            raise ValueError("Either document_id or document_set_id is required.")
        return self


class BoardSummaryResponse(BaseModel):
    document_id: UUID | None = None
    document_set_id: UUID | None = None
    scope: Literal["document", "document_set"]
    summary_type: SummaryType
    memo: BoardMemo
    citations: list[Citation]
    confidence: Confidence
