from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.advisor.schemas import Citation, Confidence, LLMProviderOptions
from app.diligence.schemas import RiskRating


AIKnowledgeGovernanceCategory = Literal[
    "knowledge_classification",
    "data_lake_readiness",
    "rag_readiness",
    "enterprise_search",
    "sensitive_ip_protection",
    "slm_private_model_readiness",
    "access_controls",
    "auditability",
    "vendor_and_provider_risk",
    "cost_governance",
    "employee_enablement",
]
AIKnowledgeGovernanceOwner = Literal[
    "CTO",
    "CISO",
    "VP Engineering",
    "Data Leader",
    "Legal",
    "Compliance",
    "Product",
    "Operations",
    "Board",
]


class AIKnowledgeGovernanceRequest(LLMProviderOptions):
    document_set_id: UUID
    top_k: int = Field(default=20, ge=5, le=40)


class AIKnowledgeGovernanceFinding(BaseModel):
    category: AIKnowledgeGovernanceCategory
    title: str
    readiness: RiskRating
    confidence: Confidence
    business_impact: str
    evidence_summary: str
    missing_evidence: list[str]
    recommended_action: str
    recommended_owner: AIKnowledgeGovernanceOwner
    citations: list[Citation]


class AIKnowledgeGovernancePlan(BaseModel):
    days_1_30: list[str]
    days_31_60: list[str]
    days_61_90: list[str]


class AIKnowledgeGovernanceResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_set_id: UUID
    assessment_type: Literal["ai_knowledge_governance"] = "ai_knowledge_governance"
    overall_readiness: RiskRating
    confidence: Confidence
    executive_summary: str
    findings: list[AIKnowledgeGovernanceFinding]
    top_gaps: list[str]
    evidence_needed: list[str]
    management_questions: list[str]
    board_discussion_points: list[str]
    recommended_actions: list[str]
    ninety_day_readiness_plan: AIKnowledgeGovernancePlan = Field(alias="90_day_readiness_plan")
    limitations: list[str]
    citations: list[Citation]
