from uuid import UUID

from sqlalchemy.orm import Session

from app.diligence.service import generate_technology_due_diligence_report
from app.planning.prompts import PLAN_TYPE_OUTCOMES, PLAN_TYPE_SUMMARY, SCENARIO_ACTIONS
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
    return [
        HundredDayPlanAction(
            priority=priority,
            action=action,
            business_rationale=_scenario_business_rationale(plan_type, action),
            owner=_owner_for_action(action, plan_type),
            risk_reduction=_scenario_risk_reduction(plan_type, action),
            deliverables=_deliverables_for_action(action, plan_type),
            success_metric=_success_metric_for_action(action, plan_type),
            citations=citations,
        )
        for action in SCENARIO_ACTIONS[plan_type][phase]
    ]


def _action_from_finding(finding, plan_type: PlanType, priority: PlanPriority) -> HundredDayPlanAction:
    category = finding.category.replace("_", " ")
    action = _action_text(finding, plan_type)
    return HundredDayPlanAction(
        priority=priority,
        action=action,
        business_rationale=_finding_business_rationale(finding, plan_type),
        owner=_normalize_owner(finding.recommended_owner, category),
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
    owner = _normalize_owner(finding.recommended_owner, category)
    return [
        f"{category.title()} evidence pack with cited source excerpts and page references",
        f"Single accountable owner recorded for {category}: {owner}",
        f"Prioritized remediation backlog for {category} with due dates and severity labels",
        f"Board metric for {category} with baseline value, target value, and reporting cadence",
    ]


def _success_metric_for_finding(finding) -> str:
    category = finding.category.replace("_", " ")
    owner = _normalize_owner(finding.recommended_owner, category)
    return f"{category.title()} remediation plan approved by {owner} with dated milestones and a measurable board status metric."


def _deliverables_for_action(action: str, plan_type: PlanType) -> list[str]:
    lower = action.lower()
    if "backup" in lower or "restore" in lower:
        return [
            "Signed restore-test record for production database with elapsed recovery time",
            "Approved RTO/RPO table for each critical data store",
            "Remediation backlog for every failed restore step with owner and due date",
            "Recurring restore-test calendar entry owned by Engineering Manager",
        ]
    if "feature flag" in lower:
        return [
            "Inventory of top 5 high-risk release paths with current rollback method",
            "Feature flag rollout standard approved by Product Leader and VP Engineering",
            "First candidate release selected with flag owner and launch date",
            "Rollback decision tree naming approver, trigger metric, and time limit",
        ]
    if "observability" in lower or "dashboard" in lower:
        return [
            "Critical workflow list with service-level indicators for availability, latency, and errors",
            "Baseline incident, latency, error-rate, and deployment-frequency metrics",
            "Executive operating dashboard published with source systems and refresh cadence",
            "Weekly metric review owner and escalation path recorded",
        ]
    if "identity" in lower or "access" in lower:
        return [
            "Privileged access inventory exported with user, role, system, and last-login fields",
            "Identity system map covering SSO, admin consoles, cloud roles, and service accounts",
            "Access exception register with remediation owner and target removal date",
            "Target-state access model approved by Security Lead and acquirer owner where applicable",
        ]
    if "knowledge" in lower or "shadow" in lower or "runbook" in lower:
        return [
            "Top 5 critical workflow list ranked by revenue, customer, and operational impact",
            "Completed shadow-session notes for each workflow with named primary and backup owner",
            "Runbooks updated with deployment, recovery, escalation, and customer-impact steps",
            "Backup owner acceptance recorded for each key dependency",
        ]
    if "cloud cost" in lower or "finops" in lower or "spend" in lower:
        return [
            "Cloud cost baseline by account, service, environment, and product area",
            "Top 10 waste or allocation gaps with estimated monthly run-rate impact",
            "FinOps review calendar with Finance and Engineering attendance",
            "Savings or allocation target approved with dollar amount and due date",
        ]
    if "data model" in lower or "migration" in lower:
        return [
            "Core entity map covering customer, account, entitlement, billing, and usage objects",
            "Migration blocker register with severity, owner, and target resolution date",
            "Validation and reconciliation plan with sample records and acceptance thresholds",
            "Migration risk register approved by Product Leader and Engineering Manager",
        ]
    if "vulnerab" in lower:
        return [
            "Critical vulnerability list with asset, exploitability, owner, and compensating control",
            "Remediation tickets opened for every critical finding",
            "Due dates assigned using severity-based SLA",
            "Executive exception report for any unresolved critical exposure",
        ]
    if "delivery cadence" in lower or "okr" in lower:
        return [
            "Prior-quarter delivery metrics covering cycle time, escaped defects, release frequency, and carryover",
            "Release cadence target approved with exception criteria",
            "Engineering OKRs mapped to top growth priorities and customer commitments",
            "Delivery operating review template with owner, metric source, and weekly agenda",
        ]
    if "ai pilot" in lower:
        return [
            "One low-risk AI pilot selected with excluded data classes documented",
            "Data governance checklist covering privacy, retention, model access, and human review",
            "Named business owner and technical owner for the pilot",
            "Pilot scorecard with success threshold, stop criteria, and review date",
        ]
    if "capacity planning" in lower:
        return [
            "Capacity model for 2x and 3x customer, traffic, and data-volume scenarios",
            "Bottleneck register with owner, cost estimate, and target mitigation date",
            "Hiring and infrastructure assumptions reviewed by Finance",
            "Board-ready capacity recommendation with spend and risk tradeoffs",
        ]
    if "scalability review" in lower:
        return [
            "Architecture review covering database, queueing, API, deployment, and observability bottlenecks",
            "Top 5 scalability risks ranked by customer and revenue impact",
            "Decision log for build, buy, defer, or retire options",
            "Modernization backlog with estimates, owners, and sequencing",
        ]
    if "hiring" in lower or "coverage plan" in lower:
        return [
            "Engineering coverage map by product area, critical system, and single-owner dependency",
            "Hiring plan with role, level, timing, and capacity gap addressed",
            "Interview loop and onboarding owner assigned for each approved role",
            "Board staffing request with budget and delivery-risk rationale",
        ]
    if "deployment" in lower or "release" in lower or "handoff" in lower:
        return [
            "Current-state deployment workflow with manual approvals and failure points identified",
            "Target release handoff checklist approved by Engineering Manager",
            "Rollback rehearsal evidence for one representative release",
            "Release ownership matrix covering acquirer, target, product, and support roles where applicable",
        ]
    if "workshop" in lower:
        return [
            "Workshop agenda covering architecture, security, deployment, support, data, and identity",
            "Attendance record with acquirer and target owners for each technical domain",
            "Decision and blocker log published within two business days",
            "Follow-up action tracker with owner and due date for each blocker",
        ]
    if "blocker" in lower:
        return [
            "Integration blocker register with severity, impact, owner, and required decision",
            "Weekly blocker review cadence with acquirer and target attendance",
            "Escalation threshold for blockers affecting close, customer continuity, or Day 1 support",
            "Closed-blocker evidence attached to the register",
        ]
    if "readout" in lower or "scorecard" in lower:
        return [
            "Board scorecard showing completed, late, deferred, and blocked actions",
            "Residual risk register with owner, impact, and next decision date",
            "Evidence appendix linking each completed action to source citations or completion artifacts",
            "Next-quarter decision log with budget, staffing, and sequencing asks",
        ]
    return [
        f"Action charter for '{action}' with scope, named owner, due date, and affected systems",
        "Milestone tracker with weekly status, blocked items, and management decisions required",
        "Evidence checklist naming each artifact required for board review",
        "Executive status metric with baseline, target, and reporting cadence",
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


def _finding_business_rationale(finding, plan_type: PlanType) -> str:
    category = finding.category.replace("_", " ")
    evidence = finding.evidence_summary.rstrip(".")
    impact = finding.business_impact.rstrip(".")
    risk = finding.risk_rationale.rstrip(".")
    scenario_clause = {
        "growth_equity": "before growth plans increase customer volume, release pressure, or operating complexity",
        "acquisition_integration": "before ownership, support, or system handoffs introduce integration risk",
        "turnaround": "before the issue continues to consume management attention, cash, or customer trust",
    }[plan_type]
    return (
        f"The {category} finding cites {evidence}. "
        f"Business impact: {impact}. "
        f"Risk rationale: {risk}. "
        f"This action creates accountable remediation evidence {scenario_clause}."
    )


def _normalize_owner(owner: str | None, category: str) -> str:
    if owner and owner.upper() == "CFO":
        return "Finance"
    if owner and owner.upper() == "CISO":
        return "CISO / Security Lead"
    if owner:
        return owner
    if "security" in category:
        return "CISO / Security Lead"
    if "cloud cost" in category:
        return "Finance"
    if "key person" in category:
        return "CEO"
    if "ai" in category:
        return "Product Leader"
    return "VP Engineering"


def _owner_for_action(action: str, plan_type: PlanType) -> str:
    lower = action.lower()
    if "spend" in lower or "cost" in lower or "finops" in lower:
        return "Finance"
    if "vulnerab" in lower or "access" in lower or "identity" in lower or "security" in lower:
        return "CISO / Security Lead"
    if "ai pilot" in lower or "data model" in lower or "migration" in lower:
        return "Product Leader"
    if "delivery cadence" in lower or "okr" in lower or "hiring" in lower or "coverage" in lower:
        return "VP Engineering"
    if "production ownership" in lower or "incident roles" in lower:
        return "CTO"
    if "runbook" in lower or "restore" in lower or "backup" in lower or "deployment" in lower or "release" in lower:
        return "Engineering Manager"
    if "workshop" in lower or "support handoff" in lower or "blocker" in lower:
        return "CTO"
    if "readout" in lower or "scorecard" in lower or "roadmap" in lower:
        return "Board"
    if plan_type == "turnaround":
        return "CEO"
    return "CTO"


def _scenario_business_rationale(plan_type: PlanType, action: str) -> str:
    lower = action.lower()
    if "feature flag" in lower:
        return "High-risk releases can delay customer commitments and create avoidable rollback risk; feature flags let product and engineering decouple launch exposure from deployment."
    if "observability" in lower:
        return "Without baseline reliability and incident metrics, management cannot tell whether scale issues are isolated events or recurring operating constraints."
    if "delivery cadence" in lower or "okr" in lower:
        return "Growth plans depend on predictable roadmap execution; reviewing cadence and OKRs exposes delivery commitments that lack capacity, ownership, or measurable outcomes."
    if "ai pilot" in lower:
        return "AI experimentation without governance can expose confidential data or create unmanaged model risk; a bounded pilot keeps learning tied to approved data and success criteria."
    if "capacity planning" in lower:
        return "A growth-equity plan requires knowing which systems, teams, and cloud costs break under higher customer and usage volume before revenue commitments are made."
    if "scalability review" in lower:
        return "Architecture bottlenecks become enterprise-value constraints when customer volume rises; a targeted review identifies the few technical decisions that most affect growth."
    if "hiring" in lower or "coverage plan" in lower:
        return "Thin engineering coverage turns roadmap growth into key-person risk; a coverage plan ties hiring to critical systems and delivery constraints."
    if "cloud cost" in lower or "finops" in lower:
        return "Cloud spend without allocation hides margin leakage and makes scaling economics hard to defend to investors or the board."
    if "modernization" in lower:
        return "Modernization work should target the bottleneck with the largest delivery or reliability impact, avoiding broad technical-debt programs without measurable business value."
    if "release automation" in lower or "deployment" in lower or "release handoff" in lower:
        return "Manual or inconsistent release practices increase outage and integration risk; standardizing the workflow makes deployment evidence reviewable and repeatable."
    if "technical debt" in lower:
        return "Debt reduction needs an operating backlog tied to incidents, delivery drag, or scalability limits so engineering capacity is spent on business-critical constraints."
    if "board operating dashboard" in lower:
        return "The board needs a concise view of delivery, reliability, and risk trends to distinguish execution progress from anecdotal management updates."
    if "technical workshops" in lower:
        return "Acquirers need direct evidence from target system owners before integration plans can be trusted; joint workshops surface hidden blockers early."
    if "parallel runbooks" in lower:
        return "Critical systems cannot rely on informal knowledge during integration; parallel runbooks preserve continuity while ownership transitions."
    if "identity" in lower or "access" in lower:
        return "Identity and privileged access gaps can create Day 1 security exposure; mapping access paths identifies exceptions before systems are connected or handed off."
    if "data model" in lower or "migration" in lower:
        return "Data mapping errors can disrupt customers, billing, and reporting; early dependency mapping reduces migration surprises and reconciliation failures."
    if "support handoff" in lower:
        return "Customer continuity depends on named support owners and escalation paths on both sides of the transaction before operational responsibility changes."
    if "knowledge transfer" in lower or "key-person" in lower or "shadow" in lower:
        return "Key-person dependency creates execution and retention risk; structured shadowing turns individual knowledge into transferable operating evidence."
    if "blocker" in lower:
        return "Integration blockers need severity, owner, and decision visibility so unresolved risks do not quietly move into post-close operations."
    if "readiness rehearsal" in lower:
        return "A rehearsal tests whether identity, data, support, and deployment plans work together before customers or employees experience the transition."
    if "spend" in lower:
        return "Uncontrolled technology spend reduces cash runway and can fund low-value work; an immediate freeze creates time to separate essential spend from waste."
    if "backup" in lower or "restore" in lower:
        return "Untested recovery is a material operating risk because management cannot prove service restoration after data loss, outage, or deployment failure."
    if "production access" in lower:
        return "Privileged production access without review increases outage, insider, and audit risk; access cleanup creates immediate control evidence."
    if "vulnerab" in lower:
        return "Critical vulnerabilities create direct security and customer-trust exposure; triage forces severity, ownership, and deadline decisions."
    if "cost-control operating cadence" in lower:
        return "Cost control only sticks when Finance and Engineering review cloud run-rate, exceptions, and savings actions on a recurring cadence."
    if "production ownership" in lower or "incident roles" in lower:
        return "Ambiguous production ownership slows incident response and lets urgent remediation drift; named roles make accountability testable."
    if "stability dashboard" in lower or "mttr" in lower:
        return "Turnaround execution requires objective stability measures so leadership can see whether incidents, MTTR, and recurring failures are improving."
    if "stabilization scorecard" in lower:
        return "The Day 100 board readout should separate completed controls from residual risk, budget decisions, and ownership gaps that still require governance."
    return f"{action} is required because the diligence evidence points to a specific operating risk that needs named ownership, measurable evidence, and board-visible follow-through."


def _scenario_risk_reduction(plan_type: PlanType, action: str) -> str:
    owner = _owner_for_action(action, plan_type)
    return f"Reduces execution risk by assigning {owner} to produce evidence that the control, handoff, or operating process is working."


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped
