from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.advisor.schemas import Citation


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
    citations: list[Citation]


class HundredDayPlanResponse(BaseModel):
    document_set_id: UUID
    plan_type: PlanType
    overall_priority: PlanPriority
    executive_summary: str
    days_1_30: list[HundredDayPlanAction]
    days_31_60: list[HundredDayPlanAction]
    days_61_90: list[HundredDayPlanAction]
    success_metrics: list[str]
    board_checkpoints: list[str]
    dependencies: list[str]
    limitations: list[str]
