from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.advisor.schemas import Citation, Confidence, LLMProviderOptions
from app.diligence.schemas import RiskRating


CRAReadinessCategory = Literal[
    "scope",
    "secure_by_design",
    "vulnerability_management",
    "sbom",
    "security_updates",
    "incident_reporting",
    "technical_documentation",
    "supplier_risk",
    "user_transparency",
    "lifecycle_support",
]
CRARecommendedOwner = Literal["CTO", "CISO", "VP Engineering", "Product", "Legal", "Compliance", "Board"]


class CRAReadinessRequest(LLMProviderOptions):
    document_set_id: UUID
    top_k: int = Field(default=20, ge=5, le=40)


class CRAReadinessFinding(BaseModel):
    category: CRAReadinessCategory
    title: str
    readiness: RiskRating
    confidence: Confidence
    business_impact: str
    evidence_summary: str
    missing_evidence: list[str]
    recommended_action: str
    recommended_owner: CRARecommendedOwner
    citations: list[Citation]


class CRAReadinessPlan(BaseModel):
    days_1_30: list[str]
    days_31_60: list[str]
    days_61_90: list[str]


class CRAReadinessResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_set_id: UUID
    assessment_type: Literal["cra_readiness"] = "cra_readiness"
    overall_readiness: RiskRating
    confidence: Confidence
    executive_summary: str
    findings: list[CRAReadinessFinding]
    top_gaps: list[str]
    evidence_needed: list[str]
    management_questions: list[str]
    board_discussion_points: list[str]
    recommended_actions: list[str]
    ninety_day_readiness_plan: CRAReadinessPlan = Field(alias="90_day_readiness_plan")
    limitations: list[str]
    citations: list[Citation]
