from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.advisor.schemas import Citation, Confidence, LLMProviderOptions
from app.diligence.schemas import RiskRating
from app.planning.schemas import HundredDayPlanResponse, PlanType


ScorecardCategory = Literal[
    "architecture",
    "security",
    "ai_governance",
    "data_handling",
    "cloud_infrastructure",
    "delivery_predictability",
    "key_person_risk",
    "technical_debt",
    "compliance_readiness",
]
RecommendedOwner = Literal["CEO", "CTO", "VP Engineering", "CISO", "CFO", "Product", "Board"]
MaturityLevel = Literal["low", "medium", "high"]


class ExecutiveModuleRequest(LLMProviderOptions):
    document_set_id: UUID
    top_k: int = Field(default=20, ge=5, le=40)


class BoardBriefRequest(ExecutiveModuleRequest):
    pass


class RiskScorecardRequest(ExecutiveModuleRequest):
    pass


class ExecutiveHundredDayPlanRequest(ExecutiveModuleRequest):
    plan_type: PlanType = "growth_equity"


class AIGovernanceAssessmentRequest(ExecutiveModuleRequest):
    pass


class RiskScorecardItem(BaseModel):
    category: ScorecardCategory
    status: RiskRating
    explanation: str
    business_impact: str
    recommended_owner: RecommendedOwner
    recommended_timeline: str
    success_metric: str
    evidence: list[Citation] = []


class TechnologyRiskScorecardResponse(BaseModel):
    document_set_id: UUID
    scorecard: list[RiskScorecardItem]
    confidence: Confidence
    limitations: list[str]


class BoardRisk(BaseModel):
    risk: str
    business_impact: str
    recommended_action: str
    evidence: list[Citation] = []


class BoardBriefResponse(BaseModel):
    document_set_id: UUID
    executive_summary: str
    top_5_technology_risks: list[BoardRisk]
    recommended_board_level_actions: list[str]
    key_decisions_needed: list[str]
    questions_for_management: list[str]
    confidence: Confidence
    citations: list[Citation]
    limitations: list[str]


class AIGovernanceAssessmentItem(BaseModel):
    category: Literal[
        "ai_use_case_clarity",
        "business_outcome_alignment",
        "data_governance",
        "data_privacy_security",
        "model_output_evaluation",
        "human_in_the_loop_controls",
        "cost_management",
        "auditability",
        "vendor_model_dependency",
        "compliance_policy_readiness",
    ]
    maturity_level: MaturityLevel
    risk_level: RiskRating
    business_impact: str
    recommended_next_step: str
    owner: RecommendedOwner
    timeline: str
    evidence: list[Citation] = []
    success_metric: str


class AIGovernanceAssessmentResponse(BaseModel):
    document_set_id: UUID
    overall_maturity: MaturityLevel
    risk_rating: RiskRating
    executive_summary: str
    items: list[AIGovernanceAssessmentItem]
    confidence: Confidence
    limitations: list[str]


class ExecutiveHundredDayPlanResponse(HundredDayPlanResponse):
    pass
