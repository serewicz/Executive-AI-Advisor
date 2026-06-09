from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisor.providers.base import SourceContext
from app.advisor.providers.factory import get_llm_provider
from app.advisor.schemas import Citation
from app.diligence.prompts import (
    ASSESSMENT_FOCUS,
    ASSESSMENT_QUERIES,
    TECHNOLOGY_DILIGENCE_SYSTEM_PROMPT,
    TECHNOLOGY_REPORT_QUERIES,
    build_diligence_prompt,
    build_technology_report_prompt,
)
from app.diligence.schemas import (
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
)
from app.diligence.scoring import (
    confidence_for_results,
    confidence_for_technology_results,
    overall_confidence,
    overall_risk_rating,
    risk_rating_for_category,
    score_assessment,
)
from app.models.document import Document, DocumentChunk, DocumentSet, DocumentSetDocument
from app.retrieval.evidence import extract_relevant_excerpt, is_low_value_chunk, relevance_reason
from app.retrieval.vector_search import SearchResult, search_similar_chunks


class DiligenceDocumentNotFoundError(ValueError):
    pass


class DiligenceValidationError(ValueError):
    pass


class DiligenceDocumentSetNotFoundError(ValueError):
    pass


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
) -> TechnologyDiligenceReport:
    document_set = db.get(DocumentSet, document_set_id)
    if document_set is None:
        raise DiligenceDocumentSetNotFoundError("Document set not found.")

    results_by_category = _retrieve_report_results_by_category(
        document_set=document_set,
        top_k=top_k,
        db=db,
    )
    all_results = _dedupe_results(
        result
        for results in results_by_category.values()
        for result in results
    )
    if not all_results:
        raise DiligenceValidationError("Document set has no chunks to analyze.")

    citation_map = _build_report_citation_map(all_results)
    findings = [
        _build_report_finding(category, results, citation_map)
        for category, results in results_by_category.items()
    ]
    risk_ratings = [finding.risk_rating for finding in findings]
    confidences = [finding.confidence for finding in findings]
    provider_draft = _draft_report_with_provider(all_results[: min(top_k, 20)])

    return TechnologyDiligenceReport(
        document_set_id=document_set.id,
        executive_summary=provider_draft.executive_summary or _build_report_executive_summary(findings),
        overall_risk_rating=overall_risk_rating(risk_ratings),
        confidence=overall_confidence([*confidences, provider_draft.confidence]),  # type: ignore[list-item]
        findings=findings,
        top_5_risks=provider_draft.top_5_risks or _build_top_risks(findings),
        management_questions=provider_draft.management_questions or _build_management_questions(findings),
        board_discussion_points=provider_draft.board_discussion_points or _build_board_discussion_points(findings),
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


def _draft_report_with_provider(results: list[SearchResult]):
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
    provider = get_llm_provider()
    return provider.generate_technology_diligence_report(
        sources=source_contexts,
        system_prompt=TECHNOLOGY_DILIGENCE_SYSTEM_PROMPT,
        user_prompt=build_technology_report_prompt(source_contexts),
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
        for query in TECHNOLOGY_REPORT_QUERIES.values()
        if any(term in result.content.lower() for term in query.lower().split()[:4])
    ) or "technology due diligence risk"


def _build_report_finding(
    category: TechnologyReportCategory,
    results: list[SearchResult],
    citation_map: dict[UUID, TechnologyDiligenceCitation],
) -> TechnologyDiligenceFinding:
    citations = [citation_map[result.chunk_id] for result in results if result.chunk_id in citation_map][:3]
    risk_rating = risk_rating_for_category(category, results)
    confidence = confidence_for_technology_results(results)
    label_text = _citation_label_text(citations)
    title = _finding_title(category, risk_rating)

    return TechnologyDiligenceFinding(
        category=category,
        title=title,
        risk_rating=risk_rating,
        confidence=confidence,
        business_impact=_business_impact(category, risk_rating, label_text),
        evidence_summary=_evidence_summary(category, results, label_text),
        recommended_action=_recommended_action(category, risk_rating),
        recommended_owner=_recommended_owner(category),
        citations=citations,
    )


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
