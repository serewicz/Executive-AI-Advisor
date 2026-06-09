from uuid import UUID

from sqlalchemy.orm import Session

from app.diligence.service import generate_technology_due_diligence_report
from app.planning.prompts import PLAN_TYPE_FOCUS, PLAN_TYPE_SUMMARY
from app.planning.schemas import (
    HundredDayPlanAction,
    HundredDayPlanResponse,
    PlanPriority,
    PlanType,
)


def generate_100_day_plan(
    document_set_id: UUID,
    plan_type: PlanType,
    db: Session,
) -> HundredDayPlanResponse:
    report = generate_technology_due_diligence_report(
        document_set_id=document_set_id,
        top_k=24,
        include_100_day_plan=True,
        db=db,
    )

    red_findings = [finding for finding in report.findings if finding.risk_rating == "red"]
    yellow_findings = [finding for finding in report.findings if finding.risk_rating == "yellow"]
    green_findings = [finding for finding in report.findings if finding.risk_rating == "green"]

    days_1_30 = [_action_from_finding(finding, plan_type, "high") for finding in red_findings]
    days_31_60 = [_action_from_finding(finding, plan_type, "medium") for finding in yellow_findings]
    days_61_90 = [_action_from_finding(finding, plan_type, "low") for finding in green_findings]

    return HundredDayPlanResponse(
        document_set_id=report.document_set_id,
        plan_type=plan_type,
        overall_priority=_overall_priority(report.overall_risk_rating),
        executive_summary=_executive_summary(plan_type, report.overall_risk_rating),
        days_1_30=days_1_30,
        days_31_60=days_31_60,
        days_61_90=days_61_90,
        success_metrics=_success_metrics(plan_type, report.findings),
        board_checkpoints=_board_checkpoints(plan_type),
        dependencies=_dependencies(plan_type, report.findings),
        limitations=[
            "Plan is generated from Technology Due Diligence Report findings and does not regenerate findings independently.",
            "Actions should be validated with management before execution.",
            "Timing is directional and should be adjusted for team capacity, business constraints, and diligence findings.",
            "No legal, financial, investment, or regulatory advice is provided.",
        ],
    )


def _action_from_finding(finding, plan_type: PlanType, priority: PlanPriority) -> HundredDayPlanAction:
    focus = ", ".join(PLAN_TYPE_FOCUS[plan_type])
    category = finding.category.replace("_", " ")
    return HundredDayPlanAction(
        priority=priority,
        action=_action_text(finding, plan_type),
        business_rationale=(
            f"{finding.business_impact} This action supports the {plan_type.replace('_', ' ')} focus on {focus}."
        ),
        owner=finding.recommended_owner,
        risk_reduction=f"Reduces {category} exposure by addressing: {finding.risk_rationale}",
        citations=finding.citations,
    )


def _action_text(finding, plan_type: PlanType) -> str:
    category = finding.category.replace("_", " ")
    if plan_type == "acquisition_integration":
        return f"Create an acquisition integration workstream for {category}: {finding.recommended_action}"
    if plan_type == "turnaround":
        return f"Stabilize {category} risk with owner, deadline, and weekly operating cadence: {finding.recommended_action}"
    return f"Execute growth-readiness action for {category}: {finding.recommended_action}"


def _overall_priority(risk_rating: str) -> PlanPriority:
    if risk_rating == "red":
        return "high"
    if risk_rating == "yellow":
        return "medium"
    return "low"


def _executive_summary(plan_type: PlanType, risk_rating: str) -> str:
    return (
        f"This 100-day technology plan is designed to {PLAN_TYPE_SUMMARY[plan_type]}. "
        f"The overall diligence risk rating is {risk_rating}; actions are sequenced so red risks are addressed "
        "in days 1-30, yellow risks in days 31-60, and green findings are monitored or improved in days 61-90."
    )


def _success_metrics(plan_type: PlanType, findings) -> list[str]:
    metrics = [
        "Backup restore tested",
        "MFA coverage reaches 100%",
        "Production deployment documented",
        "Successor identified for critical roles",
        "Cloud cost visibility dashboard deployed",
    ]
    if plan_type == "acquisition_integration":
        metrics.extend(
            [
                "Identity integration plan approved",
                "Support transition owner assigned",
                "Critical system runbooks reviewed with acquiring team",
            ]
        )
    if plan_type == "turnaround":
        metrics.extend(
            [
                "Weekly technology risk review operating cadence established",
                "Top cost-control actions assigned to owners",
            ]
        )

    categories = {finding.category for finding in findings}
    if "ai_readiness" in categories:
        metrics.append("AI governance owner and review process established")
    if "engineering_org" in categories:
        metrics.append("Engineering ownership map approved")
    return _dedupe(metrics)


def _board_checkpoints(plan_type: PlanType) -> list[str]:
    plan_focus = PLAN_TYPE_SUMMARY[plan_type]
    return [
        f"30 days: Have owners been assigned for the highest-priority technology risks supporting {plan_focus}?",
        "60 days: Are remediation plans funded, staffed, and moving against measurable milestones?",
        "90 days: Which residual risks remain open, and what board-level decisions are required?",
    ]


def _dependencies(plan_type: PlanType, findings) -> list[str]:
    dependencies = [
        "Management access to source evidence and system owners",
        "Engineering leadership capacity to validate and execute remediation",
        "Board or sponsor alignment on priority, budget, and risk appetite",
    ]
    owner_dependencies = [f"{finding.recommended_owner} availability for {finding.category.replace('_', ' ')}" for finding in findings[:5]]
    if plan_type == "acquisition_integration":
        dependencies.append("Acquirer integration team availability for identity, support, and data migration planning")
    return _dedupe([*dependencies, *owner_dependencies])


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
