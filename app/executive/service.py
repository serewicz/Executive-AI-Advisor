from uuid import UUID

from sqlalchemy.orm import Session

from app.diligence.schemas import TechnologyDiligenceFinding, TechnologyDiligenceReport
from app.diligence.service import generate_technology_due_diligence_report
from app.executive.schemas import (
    AIGovernanceAssessmentItem,
    AIGovernanceAssessmentResponse,
    BoardBriefResponse,
    BoardRisk,
    RiskScorecardItem,
    TechnologyRiskScorecardResponse,
)
from app.planning.schemas import PlanType
from app.planning.service import generate_100_day_plan


SCORECARD_CATEGORIES = {
    "architecture": {
        "finding_categories": {"architecture", "integration_readiness"},
        "owner": "CTO",
        "timeline": "Days 31-60",
        "metric": "Architecture decision log and modernization backlog approved with owners and dates.",
    },
    "security": {
        "finding_categories": {"security"},
        "owner": "CISO",
        "timeline": "Days 1-30",
        "metric": "Critical security gaps have remediation owners, due dates, and exception reporting.",
    },
    "ai_governance": {
        "finding_categories": {"ai_readiness"},
        "owner": "CTO",
        "timeline": "Days 31-60",
        "metric": "Approved AI use case inventory, data policy, review process, and pilot scorecard.",
    },
    "data_handling": {
        "finding_categories": {"ai_readiness", "security", "integration_readiness"},
        "owner": "CISO",
        "timeline": "Days 31-60",
        "metric": "Sensitive data flows and access controls documented for critical systems.",
    },
    "cloud_infrastructure": {
        "finding_categories": {"cloud_cost", "architecture"},
        "owner": "CTO",
        "timeline": "Days 31-60",
        "metric": "Cloud cost, reliability, and capacity dashboard reviewed monthly with Finance and Engineering.",
    },
    "delivery_predictability": {
        "finding_categories": {"engineering_org", "technical_debt"},
        "owner": "VP Engineering",
        "timeline": "Days 31-60",
        "metric": "Release cadence, cycle time, defect rate, and carryover are reported in the operating review.",
    },
    "key_person_risk": {
        "finding_categories": {"key_person_risk", "engineering_org"},
        "owner": "CEO",
        "timeline": "Days 1-30",
        "metric": "Critical workflows have documented primary and backup owners.",
    },
    "technical_debt": {
        "finding_categories": {"technical_debt", "architecture"},
        "owner": "VP Engineering",
        "timeline": "Days 61-100",
        "metric": "Technical debt backlog is prioritized by business impact and delivery drag.",
    },
    "compliance_readiness": {
        "finding_categories": {"security", "ai_readiness", "integration_readiness"},
        "owner": "CISO",
        "timeline": "Days 31-60",
        "metric": "Compliance evidence register is mapped to systems, owners, and review cadence.",
    },
}


AI_GOVERNANCE_CATEGORIES = {
    "ai_use_case_clarity": ("AI use cases lack clear approval criteria or business ownership.", "CTO"),
    "business_outcome_alignment": ("AI initiatives may not be tied to measurable business outcomes.", "CEO"),
    "data_privacy_security": ("AI adoption may expose sensitive data without clear controls.", "CISO"),
    "model_output_evaluation": ("Model outputs need quality, safety, and accuracy evaluation before operational reliance.", "CTO"),
    "human_in_the_loop_controls": ("High-impact AI workflows need explicit human review and escalation paths.", "Product"),
    "cost_management": ("AI usage needs spend tracking, limits, and ownership before broad rollout.", "CFO"),
    "auditability": ("AI decisions and outputs need traceability for governance and management review.", "CISO"),
    "vendor_model_dependency": ("Model or vendor concentration can create continuity, cost, or data residency risk.", "CTO"),
    "compliance_policy_readiness": ("AI policy readiness should be validated against privacy, security, and sector obligations.", "Board"),
}


AI_GOVERNANCE_SUCCESS_METRICS = {
    "ai_use_case_clarity": "Approved AI use case inventory includes business owner, intended outcome, risk tier, and review date.",
    "business_outcome_alignment": "Each approved AI initiative has a measurable business outcome and executive sponsor.",
    "data_privacy_security": "AI workflows have documented data classifications, access controls, and prohibited data handling rules.",
    "model_output_evaluation": "Model outputs are evaluated against documented quality, safety, and accuracy criteria before rollout.",
    "human_in_the_loop_controls": "High-impact AI workflows include named human reviewers, escalation paths, and exception handling.",
    "cost_management": "AI usage has budget owner, spend dashboard, and threshold alerts reviewed monthly.",
    "auditability": "AI prompts, outputs, decisions, approvals, and exceptions are traceable for management review.",
    "vendor_model_dependency": "Critical AI vendors and models have documented risk review, fallback options, and renewal ownership.",
    "compliance_policy_readiness": "AI policies map to privacy, security, sector, and board governance obligations with evidence artifacts.",
}


def generate_risk_scorecard(
    document_set_id: UUID,
    db: Session,
    top_k: int = 20,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> TechnologyRiskScorecardResponse:
    report = _build_report(document_set_id, db, top_k, llm_provider, llm_model, llm_api_key)
    return TechnologyRiskScorecardResponse(
        document_set_id=document_set_id,
        scorecard=_scorecard_items(report),
        confidence=report.confidence,
        limitations=report.limitations,
    )


def generate_board_brief(
    document_set_id: UUID,
    db: Session,
    top_k: int = 20,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> BoardBriefResponse:
    report = _build_report(document_set_id, db, top_k, llm_provider, llm_model, llm_api_key)
    scorecard = _scorecard_items(report)
    risks = [
        BoardRisk(
            risk=finding.title,
            business_impact=finding.business_impact,
            recommended_action=finding.recommended_action,
            evidence=finding.citations,
        )
        for finding in _top_findings(report)[:5]
    ]
    if len(risks) < 5:
        risks.extend(
            BoardRisk(
                risk=f"{item.category.replace('_', ' ').title()} requires management review",
                business_impact=item.business_impact,
                recommended_action=f"{item.recommended_owner} should complete the recommended action on the {item.recommended_timeline} timeline.",
                evidence=item.evidence,
            )
            for item in scorecard[: 5 - len(risks)]
        )

    return BoardBriefResponse(
        document_set_id=document_set_id,
        executive_summary=report.executive_summary,
        top_5_technology_risks=risks[:5],
        recommended_board_level_actions=[
            "Confirm accountable owners for red and yellow technology risks.",
            "Require management to provide evidence for remediation progress at each board update.",
            "Approve the operating cadence for technology risk, AI governance, security, and delivery metrics.",
            "Ask management to quantify customer, revenue, margin, and integration impact for unresolved risks.",
            "Review whether current leadership capacity is sufficient for the required remediation timeline.",
        ],
        key_decisions_needed=[
            f"Decide whether {item.recommended_owner} has authority and resources to address {item.category.replace('_', ' ')} by {item.recommended_timeline}."
            for item in scorecard[:5]
        ],
        questions_for_management=[
            *report.management_questions[:3],
            "Which technology risks could materially affect growth, customer trust, integration, or operating margin?",
            "What evidence will management provide at the next board meeting to show measurable progress?",
        ][:6],
        confidence=report.confidence,
        citations=report.citations,
        limitations=report.limitations,
    )


def generate_executive_100_day_plan(
    document_set_id: UUID,
    plan_type: PlanType,
    db: Session,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
):
    return generate_100_day_plan(
        document_set_id=document_set_id,
        plan_type=plan_type,
        db=db,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
    )


def generate_ai_governance_assessment(
    document_set_id: UUID,
    db: Session,
    top_k: int = 20,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> AIGovernanceAssessmentResponse:
    report = _build_report(document_set_id, db, top_k, llm_provider, llm_model, llm_api_key)
    ai_findings = [finding for finding in report.findings if finding.category == "ai_readiness"]
    fallback_findings = ai_findings or _top_findings(report)[:2]
    status = _aggregate_status(fallback_findings)
    maturity = _maturity_from_status(status, fallback_findings)
    evidence = [citation for finding in fallback_findings for citation in finding.citations][:3]

    return AIGovernanceAssessmentResponse(
        document_set_id=document_set_id,
        overall_maturity=maturity,
        risk_rating=status,
        executive_summary=(
            "AI governance should be treated as an executive operating discipline covering use cases, data, "
            "model evaluation, human review, cost, vendor dependency, and auditability."
        ),
        items=[
            AIGovernanceAssessmentItem(
                category=category,  # type: ignore[arg-type]
                maturity_level=maturity,
                risk_level=status,
                business_impact=_ai_business_impact(category, issue),
                recommended_next_step=_ai_next_step(category),
                owner=owner,  # type: ignore[arg-type]
                timeline=_timeline_for_status(status),
                evidence=evidence,
                success_metric=AI_GOVERNANCE_SUCCESS_METRICS[category],
            )
            for category, (issue, owner) in AI_GOVERNANCE_CATEGORIES.items()
        ],
        confidence=report.confidence,
        limitations=[
            "Assessment is limited to evidence in the active investigation workspace.",
            "AI governance maturity is directional and should be validated with management interviews and policy artifacts.",
            *report.limitations,
        ],
    )


def _build_report(
    document_set_id: UUID,
    db: Session,
    top_k: int,
    llm_provider: str | None,
    llm_model: str | None,
    llm_api_key: str | None,
) -> TechnologyDiligenceReport:
    return generate_technology_due_diligence_report(
        document_set_id=document_set_id,
        top_k=top_k,
        include_100_day_plan=True,
        db=db,
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
    )


def _scorecard_items(report: TechnologyDiligenceReport) -> list[RiskScorecardItem]:
    return [
        _scorecard_item(category, metadata, report.findings)
        for category, metadata in SCORECARD_CATEGORIES.items()
    ]


def _scorecard_item(category: str, metadata: dict, findings: list[TechnologyDiligenceFinding]) -> RiskScorecardItem:
    matched = [
        finding for finding in findings if finding.category in metadata["finding_categories"]
    ]
    status = _aggregate_status(matched)
    leading = _leading_finding(matched)
    explanation = (
        leading.evidence_summary
        if leading
        else f"No material {category.replace('_', ' ')} issue was directly evidenced in the selected documents."
    )
    business_impact = (
        leading.business_impact
        if leading
        else f"Limited evidence reduces confidence that {category.replace('_', ' ')} risk is fully understood."
    )
    evidence = [citation for finding in matched for citation in finding.citations][:3]
    return RiskScorecardItem(
        category=category,  # type: ignore[arg-type]
        status=status,
        explanation=explanation,
        business_impact=business_impact,
        recommended_owner=metadata["owner"],
        recommended_timeline=_timeline_for_status(status, metadata["timeline"]),
        success_metric=metadata["metric"],
        evidence=evidence,
    )


def _top_findings(report: TechnologyDiligenceReport) -> list[TechnologyDiligenceFinding]:
    order = {"red": 0, "yellow": 1, "green": 2}
    return _sort_findings(report.findings)


def _leading_finding(findings: list[TechnologyDiligenceFinding]) -> TechnologyDiligenceFinding | None:
    sorted_findings = _sort_findings(findings)
    return sorted_findings[0] if sorted_findings else None


def _sort_findings(findings: list[TechnologyDiligenceFinding]) -> list[TechnologyDiligenceFinding]:
    order = {"red": 0, "yellow": 1, "green": 2}
    return sorted(findings, key=lambda finding: (order[finding.risk_rating], -len(finding.citations)))


def _aggregate_status(findings: list[TechnologyDiligenceFinding]) -> str:
    statuses = [finding.risk_rating for finding in findings]
    if "red" in statuses:
        return "red"
    if "yellow" in statuses or not statuses:
        return "yellow"
    return "green"


def _timeline_for_status(status: str, default: str | None = None) -> str:
    if status == "red":
        return "Days 1-30"
    if status == "yellow":
        return default or "Days 31-60"
    return "Days 61-100"


def _maturity_from_status(status: str, findings: list[TechnologyDiligenceFinding]) -> str:
    if status == "green" and findings:
        return "high"
    if status == "red":
        return "low"
    return "medium"


def _ai_business_impact(category: str, issue: str) -> str:
    return f"{issue} Without ownership and evidence, AI adoption can create cost, security, trust, compliance, or execution risk."


def _ai_next_step(category: str) -> str:
    readable = category.replace("_", " ")
    return f"Create a documented {readable} control with owner, review cadence, success metric, and evidence artifact."
