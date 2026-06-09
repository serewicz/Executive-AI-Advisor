from uuid import UUID

from sqlalchemy.orm import Session

from app.diligence.service import generate_technology_due_diligence_report
from app.planning.prompts import PLAN_TYPE_FOCUS, PLAN_TYPE_OUTCOMES, PLAN_TYPE_SUMMARY, SCENARIO_ACTIONS
from app.planning.schemas import (
    BoardCheckpoint,
    HundredDayPlanAction,
    HundredDayPlanResponse,
    PlanAtAGlanceRow,
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

    days_1_30 = [
        *_scenario_actions(plan_type, "days_1_30", "high", red_findings),
        *[_action_from_finding(finding, plan_type, "high") for finding in red_findings],
    ]
    days_31_60 = [
        *_scenario_actions(plan_type, "days_31_60", "medium", yellow_findings),
        *[_action_from_finding(finding, plan_type, "medium") for finding in yellow_findings],
    ]
    days_61_90 = [
        *_scenario_actions(plan_type, "days_61_90", "low", green_findings),
        *[_action_from_finding(finding, plan_type, "low") for finding in green_findings],
    ]
    days_91_100 = _scenario_actions(plan_type, "days_91_100", "medium", report.findings)

    return HundredDayPlanResponse(
        document_set_id=report.document_set_id,
        plan_type=plan_type,
        overall_priority=_overall_priority(report.overall_risk_rating),
        executive_summary=_executive_summary(plan_type, report.overall_risk_rating),
        plan_at_a_glance=_plan_at_a_glance(plan_type),
        quick_wins=_quick_wins(plan_type),
        days_1_30=days_1_30,
        days_31_60=days_31_60,
        days_61_90=days_61_90,
        days_91_100=days_91_100,
        success_metrics=_success_metrics(plan_type, report.findings),
        board_checkpoints=_board_checkpoints(plan_type),
        dependencies=_dependencies(plan_type, report.findings),
        limitations=_limitations(plan_type),
    )


def _scenario_actions(
    plan_type: PlanType,
    phase: str,
    priority: PlanPriority,
    findings,
) -> list[HundredDayPlanAction]:
    citations = _phase_citations(findings)
    owner = _default_owner(plan_type)
    return [
        HundredDayPlanAction(
            priority=priority,
            action=action,
            business_rationale=_scenario_business_rationale(plan_type, action),
            owner=owner,
            risk_reduction=_scenario_risk_reduction(plan_type, action),
            deliverables=_deliverables_for_action(action, plan_type),
            success_metric=_success_metric_for_action(action, plan_type),
            citations=citations,
        )
        for action in SCENARIO_ACTIONS[plan_type][phase]
    ]


def _action_from_finding(finding, plan_type: PlanType, priority: PlanPriority) -> HundredDayPlanAction:
    focus = ", ".join(PLAN_TYPE_FOCUS[plan_type])
    category = finding.category.replace("_", " ")
    action = _action_text(finding, plan_type)
    return HundredDayPlanAction(
        priority=priority,
        action=action,
        business_rationale=(
            f"{finding.business_impact} This action supports the {plan_type.replace('_', ' ')} focus on {focus}."
        ),
        owner=finding.recommended_owner,
        risk_reduction=f"Reduces {category} exposure by addressing: {finding.risk_rationale}",
        deliverables=_deliverables_for_finding(finding),
        success_metric=_success_metric_for_finding(finding),
        citations=finding.citations,
    )


def _action_text(finding, plan_type: PlanType) -> str:
    category = finding.category.replace("_", " ")
    if plan_type == "acquisition_integration":
        return f"Create an acquisition integration workstream for {category}: {finding.recommended_action}"
    if plan_type == "turnaround":
        return f"Stabilize {category} risk with owner, deadline, and weekly operating cadence: {finding.recommended_action}"
    return f"Execute growth-readiness action for {category}: {finding.recommended_action}"


def _deliverables_for_finding(finding) -> list[str]:
    category = finding.category.replace("_", " ")
    return [
        f"Confirmed evidence pack for {category}",
        f"Named accountable owner for {category}",
        f"Remediation backlog for {category} gaps",
        f"Board-visible metric for {category} progress",
    ]


def _success_metric_for_finding(finding) -> str:
    category = finding.category.replace("_", " ")
    return f"{category.title()} action plan approved by {finding.recommended_owner} with owner, milestone, and status metric."


def _deliverables_for_action(action: str, plan_type: PlanType) -> list[str]:
    lower = action.lower()
    if "backup" in lower or "restore" in lower:
        return [
            "Complete restore test for production database",
            "Document RTO/RPO assumptions",
            "Create remediation backlog for failed restore gaps",
            "Assign owner for recurring restore testing",
        ]
    if "feature flag" in lower:
        return [
            "Inventory high-risk release paths",
            "Define feature flag rollout standards",
            "Select first release candidate for feature flagging",
            "Document rollback owner and approval path",
        ]
    if "observability" in lower or "dashboard" in lower:
        return [
            "Define critical service health indicators",
            "Baseline incident, latency, error, and deployment metrics",
            "Publish executive operating dashboard",
            "Assign owner for weekly metric review",
        ]
    if "identity" in lower or "access" in lower:
        return [
            "Inventory privileged access",
            "Map identity systems and role groups",
            "Identify access exceptions and remediation owners",
            "Approve target-state access model",
        ]
    if "knowledge" in lower or "shadow" in lower or "runbook" in lower:
        return [
            "Identify top critical workflows",
            "Complete shadow sessions with named owners",
            "Create or update critical system runbooks",
            "Confirm backup owner for each key dependency",
        ]
    if "cloud cost" in lower or "finops" in lower or "spend" in lower:
        return [
            "Create cloud cost baseline",
            "Identify top waste and allocation gaps",
            "Assign FinOps review owner",
            "Publish savings or allocation target",
        ]
    if "data model" in lower or "migration" in lower:
        return [
            "Map core entities and data owners",
            "Identify migration blockers",
            "Define validation and reconciliation approach",
            "Approve migration risk register",
        ]
    if "vulnerab" in lower:
        return [
            "Triage critical vulnerabilities",
            "Assign remediation owners",
            "Set remediation due dates",
            "Report unresolved critical exposure to executive sponsor",
        ]
    if "delivery cadence" in lower or "okr" in lower:
        return [
            "Review delivery metrics for prior quarter",
            "Define release cadence target",
            "Align engineering OKRs to growth priorities",
            "Publish delivery operating review template",
        ]
    if "ai pilot" in lower:
        return [
            "Select one low-risk AI pilot",
            "Define data governance and approval criteria",
            "Assign business owner and technical owner",
            "Document success and stop criteria",
        ]
    return [
        f"Define scope and owner for {action}",
        "Create milestone plan and operating cadence",
        "Identify evidence required for board review",
        "Publish status metric for executive review",
    ]


def _success_metric_for_action(action: str, plan_type: PlanType) -> str:
    lower = action.lower()
    if "backup" in lower or "restore" in lower:
        return "Restore test completed and reviewed by CTO by Day 30."
    if "feature flag" in lower:
        return "Feature flag rollout standard approved and first candidate release selected by Day 30."
    if "observability" in lower:
        return "Observability baseline published for top critical workflows by Day 30."
    if "deployment" in lower or "release" in lower:
        return "Deployment frequency improves from weekly to at least twice weekly where release risk allows."
    if "access" in lower or "identity" in lower:
        return "100% privileged access reviewed with exceptions assigned to owners."
    if "cloud cost" in lower or "finops" in lower or "spend" in lower:
        return "Cloud run-rate reduced by 10-15% where waste is identified, or allocation dashboard deployed."
    if "knowledge" in lower or "shadow" in lower:
        return "Knowledge transfer completed for top 3 key-person dependencies."
    if "runbook" in lower:
        return "Critical system runbooks completed for top 5 workflows."
    if "migration" in lower or "data model" in lower:
        return "Integration data mapping completed for core entities."
    if "vulnerab" in lower:
        return "Critical vulnerabilities triaged with owner and remediation date by Day 30."
    if "mttr" in lower or "stability" in lower:
        return "MTTR target under 4 hours established for priority incidents."
    if plan_type == "growth_equity":
        return "Owner, milestone, and success metric approved in growth operating review."
    if plan_type == "acquisition_integration":
        return "Acquirer and target owners sign off on integration deliverable and blocker status."
    return "Executive sponsor reviews completion evidence and residual risk by target date."


def _overall_priority(risk_rating: str) -> PlanPriority:
    if risk_rating == "red":
        return "high"
    if risk_rating == "yellow":
        return "medium"
    return "low"


def _executive_summary(plan_type: PlanType, risk_rating: str) -> str:
    outcomes = "; ".join(PLAN_TYPE_OUTCOMES[plan_type])
    return (
        f"This 100-day technology plan is designed to {PLAN_TYPE_SUMMARY[plan_type]}. "
        f"Expected outcomes: {outcomes}. The overall diligence risk rating is {risk_rating}; actions are sequenced "
        "so urgent risk is addressed first, improvement work follows, and the final board readout identifies residual "
        "risk, value creation progress, and decisions required."
    )


def _plan_at_a_glance(plan_type: PlanType) -> list[PlanAtAGlanceRow]:
    rows = {
        "growth_equity": [
            ("Days 1-30", "Establish growth operating baseline", "Feature flags, observability, OKR review, AI pilot selection", "Baseline metrics and pilot selected", "Release and scaling risk"),
            ("Days 31-60", "Plan capacity and platform leverage", "Capacity plan, scalability review, hiring plan, FinOps review", "Capacity and cost plan approved", "Growth execution risk"),
            ("Days 61-90", "Create operating leverage", "Modernization pilots, release automation, debt burn-down, board dashboard", "Automation and dashboard live", "Delivery and platform risk"),
            ("Days 91-100 / Board Readout", "Confirm next-quarter growth readiness", "Board scorecard and roadmap decisions", "Board decisions captured", "Residual scale risk"),
        ],
        "acquisition_integration": [
            ("Days 1-30", "Protect continuity and transfer knowledge", "Acquirer workshops, runbooks, identity map, data map, support handoff", "Integration owners and blocker register approved", "Integration execution risk"),
            ("Days 31-60", "Standardize operating handoffs", "Deployment handoff, key-person transfer, blocker validation", "Handoffs rehearsed with acquirer", "Continuity and ownership risk"),
            ("Days 61-90", "Rehearse integration readiness", "Identity, data, support, deployment readiness rehearsal", "Priority blockers closed or escalated", "Post-close disruption risk"),
            ("Days 91-100 / Board Readout", "Confirm close/post-close decisions", "Board readout on blockers and continuity risks", "Decisions and owners confirmed", "Residual integration risk"),
        ],
        "turnaround": [
            ("Days 1-30", "Stop the bleeding", "Spend freeze, backup test, shadow sessions, access review, vulnerability triage", "Urgent controls completed", "Operational and security risk"),
            ("Days 31-60", "Stabilize ownership and cost controls", "Cost cadence, production ownership, recovery workflows", "Owners and cadence operating", "Execution and cost risk"),
            ("Days 61-90", "Create durable operating discipline", "Stability dashboard, debt burn-down, FinOps targets", "Dashboard live and savings targets assigned", "Recurring instability risk"),
            ("Days 91-100 / Board Readout", "Confirm residual risk and budget decisions", "Stabilization scorecard and unresolved decisions", "Board approves next actions", "Residual turnaround risk"),
        ],
    }
    return [
        PlanAtAGlanceRow(
            timeframe=timeframe,
            primary_objective=objective,
            key_actions=actions,
            success_measures=measures,
            risk_reduced=risk,
        )
        for timeframe, objective, actions, measures, risk in rows[plan_type]
    ]


def _quick_wins(plan_type: PlanType) -> list[str]:
    if plan_type != "turnaround":
        return []
    return [
        "Freeze non-critical technology spend until CFO/CTO review is complete.",
        "Complete emergency backup and restore validation.",
        "Review privileged production access and remove stale access.",
        "Begin founder/key-person shadow sessions for critical workflows.",
        "Triage critical vulnerabilities and assign remediation dates.",
    ]


def _success_metrics(plan_type: PlanType, findings) -> list[str]:
    metrics = [
        "Backup restore tested successfully",
        "100% privileged access reviewed",
        "Production deployment documented",
        "Successor identified for critical roles",
        "Cloud cost visibility dashboard deployed",
        "Critical system runbooks completed for top 5 workflows",
        "Knowledge transfer completed for top 3 key-person dependencies",
    ]
    if plan_type == "growth_equity":
        metrics.extend(
            [
                "Deployment frequency improves from weekly to at least twice weekly where release risk allows",
                "Delivery predictability dashboard includes roadmap, release, incident, and reliability metrics",
                "Initial AI pilot selected with success and stop criteria",
            ]
        )
    if plan_type == "acquisition_integration":
        metrics.extend(
            [
                "Joint technical workshops completed with acquirer-side owners",
                "Integration data mapping completed for core entities",
                "Identity integration plan approved",
                "Support transition owner assigned on both sides",
            ]
        )
    if plan_type == "turnaround":
        metrics.extend(
            [
                "Cloud run-rate reduced by 10-15% where waste is identified",
                "MTTR target under 4 hours established for priority incidents",
                "Weekly technology risk review operating cadence established",
            ]
        )

    categories = {finding.category for finding in findings}
    if "ai_readiness" in categories:
        metrics.append("AI governance owner and review process established")
    if "engineering_org" in categories:
        metrics.append("Engineering ownership map approved")
    return _dedupe(metrics)


def _board_checkpoints(plan_type: PlanType) -> list[BoardCheckpoint]:
    return [
        BoardCheckpoint(
            timeframe="Day 30",
            question="Have urgent risks been assigned to accountable owners with evidence of initial control completion?",
            evidence_requested="Owner map, completed urgent-control checklist, risk register, and cited evidence pack.",
            decision_needed="Approve any budget, personnel, or access changes required to complete remediation.",
        ),
        BoardCheckpoint(
            timeframe="Day 60",
            question="Are remediation plans staffed, funded, and moving against measurable milestones?",
            evidence_requested="Milestone tracker, delivery/cost/security metrics, integration blocker log if applicable.",
            decision_needed="Escalate under-resourced workstreams or adjust scope.",
        ),
        BoardCheckpoint(
            timeframe="Day 90",
            question="What residual technology risks remain, and which value-creation actions are ready to scale?",
            evidence_requested="Updated risk heatmap, operating dashboard, completed deliverables, and unresolved blockers.",
            decision_needed="Approve next-quarter roadmap, modernization pilots, or integration sequencing.",
        ),
        BoardCheckpoint(
            timeframe="Day 100",
            question=f"Has the {plan_type.replace('_', ' ')} plan achieved its intended operating outcome?",
            evidence_requested="Board readout with status, metrics, residual risk, dependencies, and management asks.",
            decision_needed="Confirm ongoing governance cadence and ownership for remaining actions.",
        ),
    ]


def _dependencies(plan_type: PlanType, findings) -> list[str]:
    dependencies = [
        "Management access to source evidence and system owners",
        "Engineering leadership capacity to validate and execute remediation",
        "Board or sponsor alignment on priority, budget, and risk appetite",
    ]
    owner_dependencies = [
        f"{finding.recommended_owner} availability for {finding.category.replace('_', ' ')}"
        for finding in findings[:5]
    ]
    if plan_type == "acquisition_integration":
        dependencies.extend(
            [
                "Acquirer integration team availability for identity, support, deployment, and data migration planning",
                "Named acquirer-side owners for technical workshops and handoffs",
            ]
        )
    if plan_type == "turnaround":
        dependencies.append("Assumed budget authority to freeze or redirect non-critical technology spend")
    return _dedupe([*dependencies, *owner_dependencies])


def _limitations(plan_type: PlanType) -> list[str]:
    limitations = [
        "Plan is generated from Technology Due Diligence Report findings and does not regenerate findings independently.",
        "Actions should be validated with management before execution.",
        "Timing is directional and should be adjusted for team capacity, business constraints, and diligence findings.",
        "No legal, financial, investment, or regulatory advice is provided.",
    ]
    if plan_type == "turnaround":
        limitations.append("Turnaround plan assumes authority to pause, freeze, or redirect non-critical technology spend.")
    if plan_type == "acquisition_integration":
        limitations.append("Acquisition integration plan assumes timely participation from acquirer-side technology and operations owners.")
    return limitations


def _phase_citations(findings) -> list:
    citations = []
    for finding in findings[:3]:
        citations.extend(finding.citations[:1])
    return citations


def _default_owner(plan_type: PlanType) -> str:
    if plan_type == "turnaround":
        return "CTO"
    if plan_type == "acquisition_integration":
        return "CTO"
    return "VP Engineering"


def _scenario_business_rationale(plan_type: PlanType, action: str) -> str:
    return f"{action} supports {PLAN_TYPE_SUMMARY[plan_type]}."


def _scenario_risk_reduction(plan_type: PlanType, action: str) -> str:
    return f"Reduces {plan_type.replace('_', ' ')} execution risk by creating concrete evidence, ownership, and operating cadence for: {action}."


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
