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


class AIReplicabilityRiskAssessmentRequest(ExecutiveModuleRequest):
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
        "ai_incident_response",
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


ReplicabilityCategory = Literal[
    "model_dependency",
    "proprietary_data_advantage",
    "workflow_advantage",
    "knowledge_advantage",
    "operational_advantage",
    "regulatory_advantage",
]


class AIReplicabilityRiskItem(BaseModel):
    category: ReplicabilityCategory
    risk_level: RiskRating
    replicability_driver: str
    defensibility_factor: str
    competitive_barrier: str
    evidence: list[Citation] = []
    missing_evidence: list[str]
    management_questions: list[str]
    recommendation: str


class AIReplicabilityRiskPlan(BaseModel):
    days_1_30: list[str]
    days_31_60: list[str]
    days_61_90: list[str]


class AIReplicabilityRiskAssessmentResponse(BaseModel):
    document_set_id: UUID
    overall_replicability_risk: RiskRating
    executive_summary: str
    items: list[AIReplicabilityRiskItem]
    replicability_drivers: list[str]
    defensibility_factors: list[str]
    competitive_barriers: list[str]
    evidence: list[Citation]
    missing_evidence: list[str]
    management_questions: list[str]
    board_discussion_points: list[str]
    recommendations: list[str]
    ninety_day_improvement_plan: AIReplicabilityRiskPlan
    example_findings: dict[RiskRating, str]
    confidence: Confidence
    limitations: list[str]


class ExecutiveHundredDayPlanResponse(HundredDayPlanResponse):
    pass
