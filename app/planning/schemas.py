from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.advisor.schemas import Citation
from app.diligence.schemas import RiskHeatmapRow


PlanType = Literal["growth_equity", "acquisition_integration", "turnaround"]
PlanPriority = Literal["high", "medium", "low"]


class HundredDayPlanRequest(BaseModel):
    document_set_id: UUID
    plan_type: PlanType = "growth_equity"


class HundredDayPlanAction(BaseModel):
    priority: PlanPriority
    action: str
    business_rationale: str
    owner: str
    risk_reduction: str
    deliverables: list[str]
    success_metric: str
    citations: list[Citation]


class PlanAtAGlanceRow(BaseModel):
    timeframe: str
    primary_objective: str
    key_actions: str
    success_measures: str
    risk_reduced: str


class BoardCheckpoint(BaseModel):
    timeframe: str
    question: str
    evidence_requested: str
    decision_needed: str | None = None


class ExecutiveOnePager(BaseModel):
    executive_summary: str
    current_state: str
    target_state: str
    overall_risk: str
    top_5_priorities: list[str]
    first_30_days: list[str]
    days_31_60: list[str]
    days_61_90: list[str]
    board_decisions_required: list[str]
    success_metrics: list[str]
    key_dependencies: list[str]


class HundredDayPlanResponse(BaseModel):
    document_set_id: UUID
    plan_type: PlanType
    overall_priority: PlanPriority
    executive_summary: str
    executive_one_pager: ExecutiveOnePager
    risk_heatmap: list[RiskHeatmapRow]
    plan_at_a_glance: list[PlanAtAGlanceRow]
    quick_wins: list[str] = []
    days_1_30: list[HundredDayPlanAction]
    days_31_60: list[HundredDayPlanAction]
    days_61_90: list[HundredDayPlanAction]
    days_91_100: list[HundredDayPlanAction]
    success_metrics: list[str]
    board_checkpoints: list[BoardCheckpoint]
    dependencies: list[str]
    limitations: list[str]
