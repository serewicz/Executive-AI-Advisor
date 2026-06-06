from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisor.providers.base import SourceContext
from app.advisor.schemas import Citation
from app.diligence.prompts import ASSESSMENT_FOCUS, ASSESSMENT_QUERIES, build_diligence_prompt
from app.diligence.schemas import (
    AssessmentType,
    DiligenceAssessmentResponse,
    DiligenceFinding,
    DiligenceRecommendation,
    DiligenceRisk,
)
from app.diligence.scoring import confidence_for_results, score_assessment
from app.models.document import Document, DocumentChunk
from app.retrieval.vector_search import SearchResult, search_similar_chunks


class DiligenceDocumentNotFoundError(ValueError):
    pass


class DiligenceValidationError(ValueError):
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
        )
        for chunk in chunks
        if " ".join(chunk.content.split())
    ]


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
