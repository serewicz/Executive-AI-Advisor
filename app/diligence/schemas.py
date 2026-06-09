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
TechnologyReportCategory = Literal[
    "architecture",
    "security",
    "technical_debt",
    "engineering_org",
    "key_person_risk",
    "ai_readiness",
    "cloud_cost",
    "integration_readiness",
]
RiskRating = Literal["red", "yellow", "green"]


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


class TechnologyDiligenceRequest(BaseModel):
    document_set_id: UUID
    top_k: int = Field(default=20, ge=5, le=40)
    include_100_day_plan: bool = True


class TechnologyDiligenceCitation(Citation):
    pass


class TechnologyDiligenceFinding(BaseModel):
    category: TechnologyReportCategory
    title: str
    risk_rating: RiskRating
    confidence: Confidence
    risk_rationale: str
    confidence_rationale: str
    business_impact: str
    evidence_summary: str
    recommended_action: str
    recommended_owner: Literal["CEO", "CTO", "VP Engineering", "CISO", "CFO", "Product", "Board"]
    citations: list[TechnologyDiligenceCitation]


class TechnologyDiligencePlan(BaseModel):
    days_1_30: list[str]
    days_31_60: list[str]
    days_61_90: list[str]


class TechnologyDiligenceReport(BaseModel):
    document_set_id: UUID
    report_type: Literal["technology_due_diligence"] = "technology_due_diligence"
    executive_summary: str
    overall_risk_rating: RiskRating
    confidence: Confidence
    findings: list[TechnologyDiligenceFinding]
    top_5_risks: list[str]
    management_questions: list[str]
    board_discussion_points: list[str]
    recommended_actions: list[str]
    thirty_sixty_ninety_day_plan: TechnologyDiligencePlan
    limitations: list[str]
    citations: list[TechnologyDiligenceCitation]
