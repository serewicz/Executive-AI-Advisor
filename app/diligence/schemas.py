from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.advisor.schemas import Citation, Confidence


AssessmentType = Literal[
    "architecture",
    "security",
    "technical_debt",
    "key_person_risk",
    "ai_readiness",
]


class DiligenceAnalyzeRequest(BaseModel):
    document_id: UUID
    assessment_type: AssessmentType
    top_k: int = Field(default=10, ge=3, le=25)


class DiligenceFinding(BaseModel):
    title: str
    detail: str
    source_label: str | None = None


class DiligenceRisk(BaseModel):
    title: str
    severity: Literal["low", "medium", "high"]
    detail: str
    source_label: str | None = None


class DiligenceRecommendation(BaseModel):
    title: str
    detail: str
    priority: Literal["low", "medium", "high"]


class DiligenceAssessmentResponse(BaseModel):
    document_id: UUID
    assessment_type: AssessmentType
    score: int = Field(ge=1, le=5)
    executive_summary: str
    findings: list[DiligenceFinding]
    risks: list[DiligenceRisk]
    recommendations: list[DiligenceRecommendation]
    citations: list[Citation]
    confidence: Confidence
    limitations: list[str]
