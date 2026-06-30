from uuid import UUID

from sqlalchemy.orm import Session

from app.diligence.schemas import TechnologyDiligenceFinding, TechnologyDiligenceReport
from app.diligence.service import generate_technology_due_diligence_report
from app.executive.schemas import (
    AIGovernanceAssessmentItem,
    AIGovernanceAssessmentResponse,
    AIReplicabilityRiskAssessmentResponse,
    AIReplicabilityRiskItem,
    AIReplicabilityRiskPlan,
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
    "data_governance": ("AI use depends on trusted, classified, and governed data sources.", "CTO"),
    "data_privacy_security": ("AI adoption may expose sensitive data without clear security and privacy controls.", "CISO"),
    "model_output_evaluation": ("Model outputs need quality, safety, and accuracy evaluation before operational reliance.", "CTO"),
    "human_in_the_loop_controls": ("High-impact AI workflows need explicit human review and escalation paths.", "Product"),
    "cost_management": ("AI usage needs spend tracking, limits, and ownership before broad rollout.", "CFO"),
    "auditability": ("AI decisions and outputs need traceability for governance and management review.", "CISO"),
    "vendor_model_dependency": ("Model or vendor concentration can create continuity, cost, or data residency risk.", "CTO"),
    "compliance_policy_readiness": ("AI policy readiness should be validated against privacy, security, and sector obligations.", "Board"),
    "ai_incident_response": ("AI governance should include incident response, escalation paths, post-incident review, and board reporting criteria.", "CISO"),
}


AI_GOVERNANCE_SUCCESS_METRICS = {
    "ai_use_case_clarity": "Approved AI use case inventory includes business owner, intended outcome, risk tier, and review date.",
    "business_outcome_alignment": "Each approved AI initiative has a measurable business outcome and executive sponsor.",
    "data_governance": "AI data sources have documented ownership, classification, quality expectations, and permitted use.",
    "data_privacy_security": "AI workflows have documented data classifications, access controls, and prohibited data handling rules.",
    "model_output_evaluation": "Model outputs are evaluated against documented quality, safety, and accuracy criteria before rollout.",
    "human_in_the_loop_controls": "High-impact AI workflows include named human reviewers, escalation paths, and exception handling.",
    "cost_management": "AI usage has budget owner, spend dashboard, and threshold alerts reviewed monthly.",
    "auditability": "AI prompts, outputs, decisions, approvals, and exceptions are traceable for management review.",
    "vendor_model_dependency": "Critical AI vendors and models have documented risk review, fallback options, and renewal ownership.",
    "compliance_policy_readiness": "AI policies map to privacy, security, sector, and board governance obligations with evidence artifacts.",
    "ai_incident_response": "AI incident response runbook defines incident criteria, escalation path, legal/compliance involvement, board notification criteria, and post-incident review.",
}


AI_REPLICABILITY_CATEGORIES = {
    "model_dependency": {
        "finding_categories": {"ai_readiness"},
        "driver": "Reliance on third-party models, APIs, generic prompting, or vendor features can make AI-enabled capabilities easier to reproduce.",
        "defensibility": "Lower dependency risk comes from portable orchestration, evaluation benchmarks, proprietary retrieval, and provider fallback options.",
        "barrier": "Model-agnostic architecture, proprietary evaluation data, and operational tuning make simple model substitution insufficient.",
        "missing": [
            "Approved AI architecture showing model providers, orchestration, fallback options, and evaluation criteria.",
            "Evidence that output quality depends on proprietary context rather than generic model capability.",
        ],
    },
    "proprietary_data_advantage": {
        "finding_categories": {"ai_readiness", "security", "integration_readiness"},
        "driver": "AI capabilities without proprietary, permissioned, high-quality data are more likely to be copied by competitors.",
        "defensibility": "Durability improves when proprietary datasets are governed, rights-cleared, quality-controlled, and embedded in product or operating workflows.",
        "barrier": "Exclusive data rights, accumulated customer history, data quality controls, and compounding usage data are difficult to replicate quickly.",
        "missing": [
            "Inventory of proprietary datasets, ownership, rights to use, quality controls, and AI use permissions.",
            "Evidence that proprietary data materially improves AI output quality or customer value.",
        ],
    },
    "workflow_advantage": {
        "finding_categories": {"architecture", "engineering_org", "integration_readiness"},
        "driver": "AI used as a standalone assistant is easier to copy than AI embedded into differentiated customer or operating workflows.",
        "defensibility": "Workflow depth creates advantage when AI is integrated into core systems, measured processes, and customer-specific value delivery.",
        "barrier": "Deep process integration, switching costs, adoption, and feedback loops make the full workflow harder to reproduce.",
        "missing": [
            "Workflow maps showing where AI changes cycle time, quality, cost, or customer outcomes.",
            "Adoption and performance metrics for AI-enabled workflows.",
        ],
    },
    "knowledge_advantage": {
        "finding_categories": {"ai_readiness", "engineering_org", "key_person_risk"},
        "driver": "Uncaptured institutional knowledge or generic knowledge bases reduce AI defensibility.",
        "defensibility": "Unique domain expertise, decision logic, customer context, and governed knowledge assets improve durability.",
        "barrier": "Expert-reviewed playbooks, taxonomies, decision standards, and historical case knowledge are hard to recreate without organizational experience.",
        "missing": [
            "Governed knowledge sources, playbooks, taxonomies, and decision standards used by AI systems.",
            "Evidence that expert knowledge is captured, maintained, and used consistently.",
        ],
    },
    "operational_advantage": {
        "finding_categories": {"engineering_org", "architecture", "cloud_cost", "technical_debt"},
        "driver": "AI pilots without operating discipline are easy for competitors to match and difficult to scale reliably.",
        "defensibility": "Operational advantage comes from ownership, measurement, cost control, reliability, monitoring, and continuous improvement.",
        "barrier": "A disciplined operating cadence and measurable improvement rate can make execution speed itself a competitive barrier.",
        "missing": [
            "Operating metrics for AI-enabled workflows, including quality, cost, latency, adoption, and business impact.",
            "Named owners and review cadence for AI performance and improvement.",
        ],
    },
    "regulatory_advantage": {
        "finding_categories": {"security", "ai_readiness", "integration_readiness"},
        "driver": "Weak governance, privacy, security, or auditability can make AI capabilities risky even when they are useful.",
        "defensibility": "Regulatory advantage exists when compliance, auditability, trust, and data controls allow deployment in markets competitors struggle to enter.",
        "barrier": "Certifications, audit trails, sector controls, data rights, and customer trust requirements can slow competitor replication.",
        "missing": [
            "AI governance, privacy, security, auditability, and compliance evidence for sensitive workflows.",
            "Customer or regulatory requirements mapped to AI-enabled capabilities.",
        ],
    },
}


AI_REPLICABILITY_BOARD_QUESTIONS = [
    "Could a competitor reproduce this capability within 6 months?",
    "What proprietary assets create defensibility?",
    "What switching costs exist?",
    "What knowledge assets are unique?",
    "How dependent are we on third-party model providers?",
]


AI_REPLICABILITY_EXAMPLE_FINDINGS = {
    "red": "Company is primarily a wrapper around third-party LLM APIs with limited proprietary data or workflow differentiation.",
    "yellow": "Company combines third-party models with some proprietary workflow integration and internal knowledge assets.",
    "green": "Company possesses proprietary datasets, workflow integration, governance capabilities, and operational assets that are difficult to reproduce.",
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
            "This assessment does not provide legal advice. Reporting obligations vary by jurisdiction, company role, system type, and incident type. Legal and compliance counsel should confirm applicable obligations.",
            *report.limitations,
        ],
    )


def generate_ai_replicability_risk_assessment(
    document_set_id: UUID,
    db: Session,
    top_k: int = 20,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> AIReplicabilityRiskAssessmentResponse:
    report = _build_report(document_set_id, db, top_k, llm_provider, llm_model, llm_api_key)
    items = [
        _ai_replicability_item(category, metadata, report.findings)
        for category, metadata in AI_REPLICABILITY_CATEGORIES.items()
    ]
    overall_risk = _aggregate_item_status(items)
    evidence = _unique_citations([citation for item in items for citation in item.evidence])[:6]
    missing_evidence = _unique_strings([item for finding in items for item in finding.missing_evidence])
    red_or_yellow_items = [item for item in items if item.risk_level in {"red", "yellow"}]

    return AIReplicabilityRiskAssessmentResponse(
        document_set_id=document_set_id,
        overall_replicability_risk=overall_risk,  # type: ignore[arg-type]
        executive_summary=_ai_replicability_summary(overall_risk, items),
        items=items,
        replicability_drivers=[
            item.replicability_driver for item in items if item.risk_level in {"red", "yellow"}
        ][:6],
        defensibility_factors=[item.defensibility_factor for item in items][:6],
        competitive_barriers=[item.competitive_barrier for item in items][:6],
        evidence=evidence,
        missing_evidence=missing_evidence[:10],
        management_questions=_ai_replicability_management_questions(items),
        board_discussion_points=AI_REPLICABILITY_BOARD_QUESTIONS,
        recommendations=[
            item.recommendation for item in (red_or_yellow_items or items)
        ][:6],
        ninety_day_improvement_plan=_ai_replicability_plan(overall_risk, red_or_yellow_items or items),
        example_findings=AI_REPLICABILITY_EXAMPLE_FINDINGS,  # type: ignore[arg-type]
        confidence=report.confidence,
        limitations=[
            "Assessment is limited to evidence in the active investigation workspace.",
            "AI replicability risk is directional and should be validated with product, data, customer, and management interviews.",
            "The assessment evaluates durability of AI-enabled advantage, not general technology due diligence risk.",
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


def _ai_replicability_item(
    category: str,
    metadata: dict,
    findings: list[TechnologyDiligenceFinding],
) -> AIReplicabilityRiskItem:
    matched = [
        finding for finding in findings if finding.category in metadata["finding_categories"]
    ]
    status = _aggregate_status(matched)
    leading = _leading_finding(matched)
    evidence = _unique_citations([citation for finding in matched for citation in finding.citations])[:3]
    missing_evidence = [] if evidence and status == "green" else metadata["missing"]
    recommendation = _ai_replicability_recommendation(category, status)
    driver = metadata["driver"]
    if leading and status in {"red", "yellow"}:
        driver = f"{driver} Current evidence: {leading.evidence_summary}"

    return AIReplicabilityRiskItem(
        category=category,  # type: ignore[arg-type]
        risk_level=status,  # type: ignore[arg-type]
        replicability_driver=driver,
        defensibility_factor=metadata["defensibility"],
        competitive_barrier=metadata["barrier"],
        evidence=evidence,
        missing_evidence=missing_evidence,
        management_questions=_ai_replicability_category_questions(category),
        recommendation=recommendation,
    )


def _aggregate_item_status(items: list[AIReplicabilityRiskItem]) -> str:
    statuses = [item.risk_level for item in items]
    if "red" in statuses:
        return "red"
    if "yellow" in statuses or not statuses:
        return "yellow"
    return "green"


def _ai_replicability_summary(overall_risk: str, items: list[AIReplicabilityRiskItem]) -> str:
    red_count = sum(1 for item in items if item.risk_level == "red")
    yellow_count = sum(1 for item in items if item.risk_level == "yellow")
    green_count = sum(1 for item in items if item.risk_level == "green")
    if overall_risk == "red":
        return (
            "AI replicability risk is high. The available evidence suggests competitors may be able to reproduce "
            "material AI-enabled capabilities unless management strengthens proprietary data, workflow integration, "
            "knowledge assets, governance, and operating controls."
        )
    if overall_risk == "green":
        return (
            "AI replicability risk appears low based on the selected evidence. The company shows signs of durable "
            "advantage through defensible assets, integrated workflows, operating discipline, or governance capabilities."
        )
    return (
        "AI replicability risk is moderate. The company appears to have some defensibility, but durability is not fully "
        f"proven across all dimensions ({red_count} red, {yellow_count} yellow, {green_count} green)."
    )


def _ai_replicability_recommendation(category: str, status: str) -> str:
    readable = category.replace("_", " ")
    if status == "red":
        return f"Treat {readable} as an immediate defensibility gap and create a 30-day evidence-backed mitigation plan."
    if status == "yellow":
        return f"Strengthen {readable} with documented ownership, metrics, and evidence that competitors cannot easily match."
    return f"Maintain {readable} as a defensibility asset and track whether the advantage continues to compound."


def _ai_replicability_category_questions(category: str) -> list[str]:
    readable = category.replace("_", " ")
    return [
        f"What evidence proves that {readable} is difficult for competitors to reproduce?",
        f"What would a capable competitor need to match our {readable} position within 6 months?",
        f"Which executive owns the durability and measurement of {readable}?",
    ]


def _ai_replicability_management_questions(items: list[AIReplicabilityRiskItem]) -> list[str]:
    prioritized = [item for item in items if item.risk_level in {"red", "yellow"}] or items
    questions = [
        "Which AI-enabled capabilities materially affect growth, margin, retention, valuation, or exit readiness?",
        *[question for item in prioritized for question in item.management_questions],
    ]
    return _unique_strings(questions)[:8]


def _ai_replicability_plan(
    overall_risk: str,
    items: list[AIReplicabilityRiskItem],
) -> AIReplicabilityRiskPlan:
    focus = [item.category.replace("_", " ") for item in items[:3]]
    focus_text = ", ".join(focus) if focus else "AI defensibility"
    return AIReplicabilityRiskPlan(
        days_1_30=[
            f"Validate the highest-risk replicability dimensions: {focus_text}.",
            "Inventory AI-enabled capabilities, model dependencies, proprietary data, workflow integrations, and knowledge assets.",
            "Collect missing evidence for board review, including data rights, workflow metrics, governance artifacts, and evaluation results.",
        ],
        days_31_60=[
            "Prioritize mitigation work that increases proprietary data use, workflow depth, knowledge capture, and provider portability.",
            "Define operating metrics for AI quality, adoption, cost, latency, business impact, and customer value.",
            "Assign executive owners for each red or yellow replicability dimension.",
        ],
        days_61_90=[
            "Review progress with the board or operating partner against evidence, metrics, and defensibility improvements.",
            "Update investment, diligence, or product roadmap assumptions based on remaining AI replicability risk.",
            f"Re-score overall replicability risk and confirm whether it has moved from {overall_risk} toward green.",
        ],
    )


def _unique_strings(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            unique.append(normalized)
            seen.add(normalized)
    return unique


def _unique_citations(citations):
    seen = set()
    unique = []
    for citation in citations:
        key = getattr(citation, "chunk_id", None) or (
            getattr(citation, "document_id", None),
            getattr(citation, "source_label", None),
            getattr(citation, "excerpt", None),
        )
        if key not in seen:
            unique.append(citation)
            seen.add(key)
    return unique
