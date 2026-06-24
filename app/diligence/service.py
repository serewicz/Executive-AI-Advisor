from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisor.providers.base import SourceContext
from app.advisor.providers.factory import get_llm_provider
from app.advisor.schemas import Citation
from app.advisor.text import normalize_text_field
from app.diligence.prompts import (
    AI_REPLICABILITY_RISK_QUERY,
    ASSESSMENT_FOCUS,
    ASSESSMENT_QUERIES,
    TECHNOLOGY_DILIGENCE_SYSTEM_PROMPT,
    TECHNOLOGY_REPORT_QUERIES,
    build_diligence_prompt,
    build_technology_report_prompt,
)
from app.diligence.schemas import (
    AIReplicabilityRiskSection,
    AssessmentType,
    DiligenceAssessmentResponse,
    DiligenceFinding,
    DiligenceRecommendation,
    DiligenceRisk,
    TechnologyDiligenceCitation,
    TechnologyDiligenceFinding,
    TechnologyDiligencePlan,
    TechnologyDiligenceReport,
    TechnologyReportCategory,
    RiskHeatmapRow,
)
from app.diligence.scoring import (
    confidence_for_results,
    confidence_for_technology_results,
    confidence_rationale_for_results,
    overall_confidence,
    overall_risk_rating,
    risk_rating_for_category,
    risk_rationale_for_category,
    score_assessment,
)
from app.core.config import settings
from app.models.document import Document, DocumentChunk, DocumentSet, DocumentSetDocument
from app.retrieval.evidence import extract_relevant_excerpt, is_low_value_chunk, relevance_reason
from app.retrieval.vector_search import SearchResult, search_similar_chunks


class DiligenceDocumentNotFoundError(ValueError):
    pass


class DiligenceValidationError(ValueError):
    pass


class DiligenceDocumentSetNotFoundError(ValueError):
    pass


RISK_HEATMAP_CATEGORY_ORDER: tuple[TechnologyReportCategory, ...] = (
    "architecture",
    "security",
    "technical_debt",
    "engineering_org",
    "key_person_risk",
    "ai_readiness",
    "cloud_cost",
    "integration_readiness",
)


def analyze_document(
    document_id: UUID,
    assessment_type: AssessmentType,
    db: Session,
    top_k: int = 10,
) -> DiligenceAssessmentResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise DiligenceDocumentNotFoundError("Document not found.")

    if document.status not in {"chunked", "embedded", "indexed"}:
        raise DiligenceValidationError("Document must be chunked or embedded before diligence analysis.")

    results = _retrieve_assessment_chunks(
        document=document,
        assessment_type=assessment_type,
        top_k=top_k,
        db=db,
    )
    if not results:
        raise DiligenceValidationError("Document has no chunks to analyze.")

    citations = _build_citations(results)
    source_contexts = _build_source_contexts(results)
    score = score_assessment(assessment_type, results)
    confidence = confidence_for_results(results)

    return DiligenceAssessmentResponse(
        document_id=document.id,
        assessment_type=assessment_type,
        score=score,
        executive_summary=_build_executive_summary(assessment_type, score, source_contexts),
        findings=_build_findings(assessment_type, source_contexts),
        risks=_build_risks(assessment_type, score, source_contexts),
        recommendations=_build_recommendations(assessment_type, score),
        citations=citations,
        confidence=confidence,
        limitations=[
            "Assessment is limited to retrieved document chunks.",
            "Scores are deterministic directional indicators, not a substitute for human diligence.",
            "No legal, financial, investment, or regulatory advice is provided.",
        ],
    )


def generate_technology_due_diligence_report(
    document_set_id: UUID,
    db: Session,
    top_k: int = 20,
    include_100_day_plan: bool = True,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
) -> TechnologyDiligenceReport:
    document_set = db.get(DocumentSet, document_set_id)
    if document_set is None:
        raise DiligenceDocumentSetNotFoundError("Document set not found.")

    results_by_category = _retrieve_report_results_by_category(
        document_set=document_set,
        top_k=top_k,
        db=db,
    )
    ai_replicability_results = _retrieve_ai_replicability_results(
        document_set=document_set,
        top_k=max(3, min(8, top_k // max(1, len(TECHNOLOGY_REPORT_QUERIES)))),
        db=db,
    )
    all_results = _dedupe_results(
        result
        for results in results_by_category.values()
        for result in results
    ) + _dedupe_results(ai_replicability_results)
    all_results = _dedupe_results(all_results)
    if not all_results:
        raise DiligenceValidationError("Document set has no chunks to analyze.")

    citation_map = _build_report_citation_map(all_results)
    findings = [
        _build_report_finding(category, results, citation_map)
        for category, results in results_by_category.items()
    ]
    ai_replicability_risk = _build_ai_replicability_risk_section(
        ai_replicability_results or results_by_category.get("ai_readiness", []),
        citation_map,
    )
    risk_ratings = [finding.risk_rating for finding in findings]
    confidences = [finding.confidence for finding in findings]
    provider_draft = _draft_report_with_provider(
        all_results[: min(top_k, 20)],
        llm_provider=llm_provider,
        llm_model=llm_model,
        llm_api_key=llm_api_key,
    )

    return TechnologyDiligenceReport(
        document_set_id=document_set.id,
        executive_summary=normalize_text_field(
            provider_draft.executive_summary or _build_report_executive_summary(findings)
        ),
        overall_risk_rating=overall_risk_rating(risk_ratings),
        confidence=overall_confidence([*confidences, provider_draft.confidence]),  # type: ignore[list-item]
        risk_heatmap=_build_risk_heatmap(findings),
        findings=findings,
        top_5_risks=provider_draft.top_5_risks or _build_top_risks(findings),
        management_questions=provider_draft.management_questions or _build_management_questions(findings),
        board_discussion_points=provider_draft.board_discussion_points or _build_board_discussion_points(findings),
        ai_replicability_risk=ai_replicability_risk,
        recommended_actions=provider_draft.recommended_actions or _build_report_recommended_actions(findings),
        thirty_sixty_ninety_day_plan=_build_report_plan(findings, include_100_day_plan),
        limitations=[
            "Report is limited to documents in the selected investigation workspace.",
            "Risk ratings are deterministic directional indicators based on retrieved evidence.",
            "The report does not provide legal, financial, investment, or regulatory advice.",
            "Management should validate cited evidence and provide corroborating artifacts before relying on findings.",
            *provider_draft.limitations,
        ],
        citations=list(citation_map.values()),
    )


def build_risk_heatmap(findings: list[TechnologyDiligenceFinding]) -> list[RiskHeatmapRow]:
    return _build_risk_heatmap(findings)


def _retrieve_report_results_by_category(
    document_set: DocumentSet,
    top_k: int,
    db: Session,
) -> dict[TechnologyReportCategory, list[SearchResult]]:
    per_category_k = max(3, min(8, top_k // max(1, len(TECHNOLOGY_REPORT_QUERIES))))
    results_by_category = {}
    for category, query in TECHNOLOGY_REPORT_QUERIES.items():
        try:
            results = search_similar_chunks(
                query=query,
                db=db,
                top_k=per_category_k,
                document_set_id=document_set.id,
            )
        except Exception:
            results = []
        if not results:
            results = _load_ordered_chunks_for_set(document_set=document_set, top_k=per_category_k, db=db)
        results_by_category[category] = _dedupe_results(results)[:per_category_k]
    return results_by_category


def _retrieve_ai_replicability_results(
    document_set: DocumentSet,
    top_k: int,
    db: Session,
) -> list[SearchResult]:
    try:
        results = search_similar_chunks(
            query=AI_REPLICABILITY_RISK_QUERY,
            db=db,
            top_k=top_k,
            document_set_id=document_set.id,
        )
    except Exception:
        results = []
    return _dedupe_results(results)[:top_k]


def _draft_report_with_provider(
    results: list[SearchResult],
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
):
    source_contexts = [
        SourceContext(
            label=f"[S{index}]",
            content=result.content,
            document_title=result.document_title,
            page_start=result.page_start,
            page_end=result.page_end,
        )
        for index, result in enumerate(results, start=1)
    ]
    provider = get_llm_provider(llm_provider)
    return provider.generate_technology_diligence_report(
        sources=source_contexts,
        system_prompt=TECHNOLOGY_DILIGENCE_SYSTEM_PROMPT,
        user_prompt=build_technology_report_prompt(source_contexts),
        api_key_override=llm_api_key,
        model_override=llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
    )


def _retrieve_assessment_chunks(
    document: Document,
    assessment_type: AssessmentType,
    top_k: int,
    db: Session,
) -> list[SearchResult]:
    if document.status in {"embedded", "indexed"}:
        try:
            results = search_similar_chunks(
                query=ASSESSMENT_QUERIES[assessment_type],
                db=db,
                top_k=top_k,
                document_id=document.id,
            )
        except Exception:
            results = []

        if results:
            return results

    return _load_ordered_chunks(document=document, top_k=top_k, db=db)


def _load_ordered_chunks(document: Document, top_k: int, db: Session) -> list[SearchResult]:
    statement = (
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document.id)
        .order_by(DocumentChunk.chunk_index)
        .limit(top_k)
    )
    chunks = db.scalars(statement).all()
    document_title = document.title or document.filename

    return [
        SearchResult(
            document_id=document.id,
            document_title=document_title,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            similarity_score=0.0,
            source_type=document.source_type,
            classification=document.classification,
            chunk_metadata=chunk.chunk_metadata or {},
        )
        for chunk in chunks
        if _is_useful_chunk(chunk)
    ]


def _load_ordered_chunks_for_set(document_set: DocumentSet, top_k: int, db: Session) -> list[SearchResult]:
    statement = (
        select(DocumentChunk, Document)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(DocumentSetDocument, DocumentSetDocument.document_id == Document.id)
        .where(DocumentSetDocument.document_set_id == document_set.id)
        .order_by(Document.uploaded_at.desc(), DocumentChunk.chunk_index)
        .limit(top_k)
    )
    rows = db.execute(statement).all()
    return [
        SearchResult(
            document_id=document.id,
            document_title=document.title or document.filename,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            similarity_score=0.0,
            source_type=document.source_type,
            classification=document.classification,
            chunk_metadata=chunk.chunk_metadata or {},
        )
        for chunk, document in rows
        if _is_useful_chunk(chunk)
    ]


def _is_useful_chunk(chunk: DocumentChunk) -> bool:
    normalized = " ".join(chunk.content.split())
    if not normalized:
        return False
    return not bool((chunk.chunk_metadata or {}).get("low_value")) and not is_low_value_chunk(normalized)


def _dedupe_results(results: Iterable[SearchResult]) -> list[SearchResult]:
    deduped = []
    seen = set()
    for result in results:
        if result.chunk_id in seen or result.low_value:
            continue
        if is_low_value_chunk(result.content):
            continue
        seen.add(result.chunk_id)
        deduped.append(result)
    return deduped


def _build_report_citation_map(results: list[SearchResult]) -> dict[UUID, TechnologyDiligenceCitation]:
    citation_map = {}
    for index, result in enumerate(results, start=1):
        query = _query_for_result(result)
        excerpt = extract_relevant_excerpt(result.content, query, max_chars=500)
        citation_map[result.chunk_id] = TechnologyDiligenceCitation(
            source_label=f"S{index}",
            document_id=result.document_id,
            document_title=result.document_title,
            chunk_id=result.chunk_id,
            page_start=result.page_start,
            page_end=result.page_end,
            excerpt=excerpt,
            relevance_reason=relevance_reason(excerpt, query),
            full_source_text=result.content,
        )
    return citation_map


def _query_for_result(result: SearchResult) -> str:
    return " ".join(
        query
        for query in [*TECHNOLOGY_REPORT_QUERIES.values(), AI_REPLICABILITY_RISK_QUERY]
        if any(term in result.content.lower() for term in query.lower().split()[:4])
    ) or "technology due diligence risk"


def _build_report_finding(
    category: TechnologyReportCategory,
    results: list[SearchResult],
    citation_map: dict[UUID, TechnologyDiligenceCitation],
) -> TechnologyDiligenceFinding:
    citations = [citation_map[result.chunk_id] for result in results if result.chunk_id in citation_map][:3]
    risk_rating = risk_rating_for_category(category, results)
    confidence = confidence_for_technology_results(results, category)
    label_text = _citation_label_text(citations)
    title = _finding_title(category, risk_rating)

    return TechnologyDiligenceFinding(
        category=category,
        title=title,
        risk_rating=risk_rating,
        confidence=confidence,
        risk_rationale=risk_rationale_for_category(category, results),
        confidence_rationale=confidence_rationale_for_results(results, category),
        business_impact=_business_impact(category, risk_rating, label_text),
        evidence_summary=_evidence_summary(category, results, label_text),
        recommended_action=_recommended_action(category, risk_rating),
        recommended_owner=_recommended_owner(category),
        citations=citations,
    )


def _build_ai_replicability_risk_section(
    ai_readiness_results: list[SearchResult],
    citation_map: dict[UUID, TechnologyDiligenceCitation],
) -> AIReplicabilityRiskSection:
    results = _dedupe_results(
        result
        for result in ai_readiness_results
        if _result_matches_ai_replicability(result)
    )
    citations = [citation_map[result.chunk_id] for result in results if result.chunk_id in citation_map][:4]
    overall_rating = _ai_replicability_rating(results)
    labels = _citation_label_text(citations)

    return AIReplicabilityRiskSection(
        overall_rating=overall_rating,  # type: ignore[arg-type]
        executive_assessment=_ai_replicability_executive_assessment(overall_rating, labels),
        replicability_drivers=_ai_replicability_drivers(results, labels),
        defensibility_factors=_ai_defensibility_factors(results, labels),
        competitive_barriers=_ai_competitive_barriers(results, labels),
        evidence=citations,
        management_questions=[
            "Could a competitor reproduce this AI capability within 6 months using publicly available models, tools, services, and data?",
            "Which proprietary data, workflow, or knowledge assets materially improve AI-enabled outcomes?",
            "How dependent is the organization on third-party model providers for differentiated customer or operating value?",
            "What evidence shows that AI-enabled workflows are embedded deeply enough to create switching costs or margin protection?",
        ],
        board_discussion_points=[
            "Review whether AI-enabled value is defensible or primarily a temporary productivity improvement.",
            "Ask management to identify the evidence-backed barriers that would slow a capable competitor.",
            "Confirm whether AI replicability risk affects valuation, customer retention, margin protection, or exit readiness.",
        ],
        recommendations=_ai_replicability_recommendations(overall_rating),
    )


def _result_matches_ai_replicability(result: SearchResult) -> bool:
    text = result.content.lower()
    terms = {
        "ai",
        "model",
        "automation",
        "machine learning",
        "llm",
        "data",
        "workflow",
        "governance",
        "proprietary",
        "knowledge",
        "customer",
    }
    return any(term in text for term in terms)


def _ai_replicability_rating(results: list[SearchResult]) -> str:
    if not results:
        return "yellow"
    text = " ".join(result.content.lower() for result in results)
    red_terms = {
        "public ai",
        "public model",
        "third-party model",
        "third party model",
        "generic",
        "no proprietary",
        "limited proprietary",
        "wrapper",
        "vendor dependency",
        "model dependency",
        "no ai governance",
        "unofficial ai",
    }
    green_terms = {
        "proprietary data",
        "exclusive data",
        "workflow integration",
        "governed",
        "governance",
        "auditability",
        "human review",
        "operational maturity",
        "documented controls",
        "approved documentation",
    }
    red_score = sum(1 for term in red_terms if term in text)
    green_score = sum(1 for term in green_terms if term in text)
    if red_score >= 2 and green_score <= 1:
        return "red"
    if green_score >= 3 and red_score == 0:
        return "green"
    return "yellow"


def _ai_replicability_executive_assessment(rating: str, labels: str) -> str:
    statements = {
        "red": "High Replicability Risk: The organization's AI capability is primarily dependent on publicly available models and can likely be reproduced with limited investment.",
        "yellow": "Moderate Replicability Risk: The organization possesses workflow and knowledge advantages, but model dependency remains significant.",
        "green": "Low Replicability Risk: The organization combines proprietary data, workflow integration, operational maturity, and governance capabilities that create meaningful barriers to replication.",
    }
    suffix = f" {labels}" if labels else " Evidence is limited in the uploaded documents."
    return f"{statements[rating]}{suffix}".strip()


def _ai_replicability_drivers(results: list[SearchResult], labels: str) -> list[str]:
    if not results:
        return ["Uploaded documents do not provide enough evidence to identify specific AI replicability drivers."]
    drivers = []
    text = " ".join(result.content.lower() for result in results)
    if any(term in text for term in ["third-party", "third party", "vendor", "public model", "model dependency", "llm"]):
        drivers.append("AI capability appears dependent on third-party model or vendor capabilities.")
    if any(term in text for term in ["limited proprietary", "no proprietary", "public", "generic"]):
        drivers.append("Evidence suggests limited proprietary differentiation in AI data, models, or implementation.")
    if any(term in text for term in ["manual", "unofficial", "no ai governance", "inconsistent"]):
        drivers.append("AI use appears operationally immature or inconsistently governed.")
    if not drivers:
        drivers.append("Uploaded AI readiness evidence does not clearly establish whether capabilities are difficult to reproduce.")
    return [f"{driver} {labels}".strip() for driver in drivers]


def _ai_defensibility_factors(results: list[SearchResult], labels: str) -> list[str]:
    if not results:
        return ["No defensibility factors were directly evidenced in uploaded documents."]
    factors = []
    text = " ".join(result.content.lower() for result in results)
    if "proprietary data" in text or "customer data" in text:
        factors.append("Proprietary or customer data may support differentiated AI outputs.")
    if "workflow" in text or "automation" in text:
        factors.append("Workflow integration may create operating advantage if adoption and outcomes are measured.")
    if "knowledge" in text or "documentation" in text or "approved documentation" in text:
        factors.append("Documented knowledge assets may improve AI consistency and reduce simple replication.")
    if "governance" in text or "human review" in text or "auditability" in text:
        factors.append("Governance, review, or audit controls may support trusted AI deployment.")
    if not factors:
        factors.append("Uploaded documents do not provide direct evidence of proprietary data, workflow, knowledge, or governance advantages.")
    return [f"{factor} {labels}".strip() for factor in factors]


def _ai_competitive_barriers(results: list[SearchResult], labels: str) -> list[str]:
    if not results:
        return ["No competitive barriers were directly evidenced in uploaded documents."]
    barriers = []
    text = " ".join(result.content.lower() for result in results)
    if "proprietary data" in text or "exclusive" in text:
        barriers.append("Data access or data rights may create a barrier to competitor replication.")
    if "workflow" in text or "integration" in text:
        barriers.append("Embedded workflow integration may create switching costs or implementation friction.")
    if "governance" in text or "compliance" in text or "auditability" in text:
        barriers.append("Governance, compliance, or audit requirements may slow competitor deployment.")
    if not barriers:
        barriers.append("Uploaded documents do not directly evidence barriers that would prevent competitor replication.")
    return [f"{barrier} {labels}".strip() for barrier in barriers]


def _ai_replicability_recommendations(rating: str) -> list[str]:
    if rating == "red":
        return [
            "Request evidence of proprietary data, workflow integration, knowledge assets, and governance controls before treating AI capability as defensible.",
            "Require management to distinguish AI productivity benefits from durable competitive advantage.",
            "Assess whether valuation, retention, or margin assumptions depend on AI capabilities competitors can reproduce.",
        ]
    if rating == "green":
        return [
            "Maintain evidence of proprietary data rights, workflow integration, operating controls, and governance maturity.",
            "Track whether AI-enabled advantages continue to compound through usage, customer data, and process improvement.",
            "Include AI defensibility evidence in board, investor, and exit readiness materials.",
        ]
    return [
        "Validate which AI capabilities are meaningfully differentiated versus dependent on common model or vendor capabilities.",
        "Strengthen evidence for proprietary data, workflow integration, knowledge assets, and operating controls.",
        "Ask management to provide a 90-day plan to reduce model dependency and improve defensibility.",
    ]


def _build_risk_heatmap(findings: list[TechnologyDiligenceFinding]) -> list[RiskHeatmapRow]:
    findings_by_category = {finding.category: finding for finding in findings}
    return [
        RiskHeatmapRow(
            category=category,
            risk_rating=finding.risk_rating,
            confidence=finding.confidence,
            evidence_count=len(finding.citations),
            primary_recommended_action=finding.recommended_action,
        )
        for category in RISK_HEATMAP_CATEGORY_ORDER
        if (finding := findings_by_category.get(category)) is not None
    ]


def _citation_label_text(citations: list[TechnologyDiligenceCitation]) -> str:
    if not citations:
        return ""
    return " ".join(f"[{citation.source_label}]" for citation in citations[:3])


def _finding_title(category: TechnologyReportCategory, risk_rating: str) -> str:
    category_title = category.replace("_", " ").title()
    if risk_rating == "red":
        return f"Material {category_title} Risk"
    if risk_rating == "yellow":
        return f"Moderate {category_title} Risk"
    return f"Limited {category_title} Concern"


def _business_impact(category: TechnologyReportCategory, risk_rating: str, labels: str) -> str:
    impacts = {
        "architecture": "Platform constraints may affect reliability, scalability, integration velocity, and enterprise readiness.",
        "security": "Security governance gaps may increase customer trust, audit, incident response, and compliance exposure.",
        "technical_debt": "Technical debt may slow roadmap delivery, increase defect risk, and reduce engineering leverage.",
        "engineering_org": "Organization and ownership gaps may reduce delivery predictability and operational accountability.",
        "key_person_risk": "Knowledge concentration may create continuity risk during growth, diligence, or post-investment scaling.",
        "ai_readiness": "AI readiness gaps may limit safe automation, data leverage, and future AI-enabled product differentiation.",
        "cloud_cost": "Cloud cost controls may affect margin expansion, budget predictability, and scaling economics.",
        "integration_readiness": "Integration readiness issues may affect M&A planning, customer migration, and operating continuity.",
    }
    prefix = "Material" if risk_rating == "red" else "Moderate" if risk_rating == "yellow" else "Limited"
    return f"{prefix} concern: {impacts[category]} {labels}".strip()


def _evidence_summary(
    category: TechnologyReportCategory,
    results: list[SearchResult],
    labels: str,
) -> str:
    if not results:
        return f"No strong evidence was retrieved for {category.replace('_', ' ')}."
    documents = sorted({result.document_title for result in results})
    return (
        f"Retrieved {len(results)} relevant evidence passage(s) across "
        f"{len(documents)} document(s): {', '.join(documents[:3])}. {labels}"
    ).strip()


def _recommended_action(category: TechnologyReportCategory, risk_rating: str) -> str:
    actions = {
        "architecture": "Validate architecture ownership, scalability constraints, reliability runbooks, and integration bottlenecks with engineering leadership.",
        "security": "Request evidence for access controls, incident response, vulnerability management, audit logs, and customer data protection.",
        "technical_debt": "Quantify debt themes, remediation effort, test coverage gaps, and roadmap capacity reserved for platform hardening.",
        "engineering_org": "Review ownership maps, hiring plan, operating metrics, delivery process, and accountability model.",
        "key_person_risk": "Create a succession and knowledge transfer plan for critical systems, production operations, and customer escalations.",
        "ai_readiness": "Establish AI governance, data quality ownership, model risk controls, and prioritized AI use cases.",
        "cloud_cost": "Create FinOps ownership, budget alerts, tagging discipline, unit economics reporting, and cost optimization targets.",
        "integration_readiness": "Build an integration readiness checklist for identity, data migration, support handoff, deployment, and roadmap continuity.",
    }
    if risk_rating == "green":
        return f"Confirm current controls remain adequate and monitor for change. {actions[category]}"
    return actions[category]


def _recommended_owner(category: TechnologyReportCategory) -> str:
    owners = {
        "architecture": "CTO",
        "security": "CISO",
        "technical_debt": "VP Engineering",
        "engineering_org": "VP Engineering",
        "key_person_risk": "CEO",
        "ai_readiness": "CTO",
        "cloud_cost": "CFO",
        "integration_readiness": "Board",
    }
    return owners[category]


def _build_report_executive_summary(findings: list[TechnologyDiligenceFinding]) -> str:
    red_count = sum(1 for finding in findings if finding.risk_rating == "red")
    yellow_count = sum(1 for finding in findings if finding.risk_rating == "yellow")
    green_count = sum(1 for finding in findings if finding.risk_rating == "green")
    highest = "red" if red_count else "yellow" if yellow_count else "green"
    return (
        "The technology diligence report was generated from evidence retrieved only within the selected "
        f"investigation workspace. Overall posture is {highest}, with {red_count} red, {yellow_count} yellow, "
        f"and {green_count} green category finding(s). The board should focus on the highest-rated risks, "
        "management validation questions, and near-term remediation ownership before relying on the platform "
        "for accelerated growth."
    )


def _build_top_risks(findings: list[TechnologyDiligenceFinding]) -> list[str]:
    sorted_findings = sorted(findings, key=lambda finding: {"red": 0, "yellow": 1, "green": 2}[finding.risk_rating])
    return [
        f"{finding.title}: {finding.business_impact}"
        for finding in sorted_findings[:5]
    ]


def _build_management_questions(findings: list[TechnologyDiligenceFinding]) -> list[str]:
    return [
        f"What evidence supports management's current position on {finding.category.replace('_', ' ')}?"
        for finding in findings
        if finding.risk_rating in {"red", "yellow"}
    ][:8] or ["What evidence confirms the current technology controls remain sufficient for the next growth stage?"]


def _build_board_discussion_points(findings: list[TechnologyDiligenceFinding]) -> list[str]:
    return [
        f"Board discussion: {finding.title} and whether the proposed owner ({finding.recommended_owner}) has the mandate and resources to act."
        for finding in findings
        if finding.risk_rating in {"red", "yellow"}
    ][:8] or ["Board discussion: Confirm monitoring cadence for technology, security, AI, and cloud cost risks."]


def _build_report_recommended_actions(findings: list[TechnologyDiligenceFinding]) -> list[str]:
    return [
        f"{finding.recommended_owner}: {finding.recommended_action}"
        for finding in findings
        if finding.risk_rating in {"red", "yellow"}
    ][:8] or ["CTO: Maintain current controls and provide quarterly evidence updates to the board."]


def _build_report_plan(
    findings: list[TechnologyDiligenceFinding],
    include_100_day_plan: bool,
) -> TechnologyDiligencePlan:
    if not include_100_day_plan:
        return TechnologyDiligencePlan(days_1_30=[], days_31_60=[], days_61_90=[])

    prioritized = sorted(findings, key=lambda finding: {"red": 0, "yellow": 1, "green": 2}[finding.risk_rating])
    top_findings = prioritized[:5]
    return TechnologyDiligencePlan(
        days_1_30=[
            f"Validate evidence and assign owner for {finding.category.replace('_', ' ')}."
            for finding in top_findings[:3]
        ] or ["Validate evidence and confirm diligence scope with management."],
        days_31_60=[
            f"Create remediation plan for {finding.category.replace('_', ' ')} with milestones and board-visible metrics."
            for finding in top_findings[:3]
        ] or ["Create remediation plans for confirmed technology risks."],
        days_61_90=[
            f"Track remediation progress for {finding.category.replace('_', ' ')} and escalate blockers."
            for finding in top_findings[:3]
        ] or ["Track progress and update the board on residual technology risk."],
    )


def _build_source_contexts(results: list[SearchResult]) -> list[SourceContext]:
    return [
        SourceContext(
            label=f"[S{index}]",
            content=result.content,
            document_title=result.document_title,
            page_start=result.page_start,
            page_end=result.page_end,
        )
        for index, result in enumerate(results, start=1)
    ]


def _build_citations(results: list[SearchResult]) -> list[Citation]:
    return [
        Citation(
            source_label=f"S{index}",
            document_id=result.document_id,
            document_title=result.document_title,
            chunk_id=result.chunk_id,
            page_start=result.page_start,
            page_end=result.page_end,
            excerpt=result.content[:1000],
        )
        for index, result in enumerate(results, start=1)
    ]


def _build_executive_summary(
    assessment_type: AssessmentType,
    score: int,
    sources: list[SourceContext],
) -> str:
    label = sources[0].label
    posture = "strong" if score >= 4 else "mixed" if score == 3 else "concerning"
    return (
        f"The {assessment_type.replace('_', ' ')} assessment indicates a {posture} diligence posture "
        f"based on retrieved evidence focused on {ASSESSMENT_FOCUS[assessment_type]}. {label}"
    )


def _build_findings(assessment_type: AssessmentType, sources: list[SourceContext]) -> list[DiligenceFinding]:
    prompt_context = build_diligence_prompt(assessment_type, sources[:2])
    first = sources[0]
    second = sources[1] if len(sources) > 1 else sources[0]
    return [
        DiligenceFinding(
            title=f"{assessment_type.replace('_', ' ').title()} evidence retrieved",
            detail=(
                f"The source set contains evidence relevant to {ASSESSMENT_FOCUS[assessment_type]}. "
                f"{first.label}"
            ),
            source_label=first.label.strip("[]"),
        ),
        DiligenceFinding(
            title="Structured assessment prompt prepared",
            detail=(
                "The diligence module prepared a bounded prompt requiring sourced findings, risks, "
                f"recommendations, confidence, and limitations. {second.label}"
            ),
            source_label=second.label.strip("[]"),
        ),
    ] if prompt_context else []


def _build_risks(
    assessment_type: AssessmentType,
    score: int,
    sources: list[SourceContext],
) -> list[DiligenceRisk]:
    severity = "low" if score >= 4 else "medium" if score == 3 else "high"
    label = sources[0].label
    return [
        DiligenceRisk(
            title=f"{assessment_type.replace('_', ' ').title()} diligence risk",
            severity=severity,
            detail=(
                f"Management should validate the cited evidence before relying on this {assessment_type} posture. "
                f"{label}"
            ),
            source_label=label.strip("[]"),
        )
    ]


def _build_recommendations(
    assessment_type: AssessmentType,
    score: int,
) -> list[DiligenceRecommendation]:
    priority = "medium" if score >= 4 else "high"
    return [
        DiligenceRecommendation(
            title="Validate evidence with management",
            detail=(
                "Review cited source passages with technical leadership and request supporting artifacts "
                "for any material diligence claim."
            ),
            priority=priority,
        ),
        DiligenceRecommendation(
            title=f"Create {assessment_type.replace('_', ' ')} action plan",
            detail=(
                "Translate confirmed findings into owners, due dates, and measurable remediation or monitoring steps."
            ),
            priority=priority,
        ),
    ]
