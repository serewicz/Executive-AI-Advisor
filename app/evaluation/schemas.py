from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EvaluationQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    expected_themes: list[str] | None = None


class EvaluationResult(BaseModel):
    question: str
    answer: str
    citations: list[dict[str, Any]]
    citation_score: float = Field(ge=0.0, le=1.0)
    groundedness_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    executive_usefulness_score: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    notes: list[str]


class EvaluationRunRequest(BaseModel):
    document_id: UUID
    evaluation_type: str = Field(default="advisor_qa", min_length=1, max_length=100)
    questions: list[EvaluationQuestion] = Field(min_length=1)


class EvaluationRunResponse(BaseModel):
    evaluation_run_id: UUID
    document_id: UUID | None
    evaluation_type: str
    average_score: float = Field(ge=0.0, le=1.0)
    results: list[EvaluationResult]
