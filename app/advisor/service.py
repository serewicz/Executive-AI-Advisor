from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.advisor.prompts import (
    BOARD_SUMMARY_SYSTEM_PROMPT,
    SUMMARY_TYPE_QUERIES,
    SYSTEM_PROMPT,
    build_board_summary_prompt,
    build_user_prompt,
)
from app.advisor.providers.base import SourceContext
from app.advisor.providers.factory import get_llm_provider
from app.advisor.schemas import (
    AdvisorAskResponse,
    AdvisorCitation,
    BoardMemo,
    BoardSummaryResponse,
    Citation,
    SummaryType,
)
from app.models.document import Document, DocumentChunk, DocumentSet, DocumentSetDocument
from app.retrieval.evidence import (
    extract_relevant_excerpt,
    is_low_value_chunk,
    relevance_reason,
)
from app.retrieval.vector_search import SearchResult, search_similar_chunks


class AdvisorDocumentNotFoundError(ValueError):
    pass


class AdvisorValidationError(ValueError):
    pass


def answer_executive_question(
    question: str,
    db: Session,
    top_k: int = 5,
    source_type: str | None = None,
    classification: str | None = None,
    document_id: UUID | None = None,
    document_set_id: UUID | None = None,
) -> AdvisorAskResponse:
    scope = "document" if document_id is not None else "document_set" if document_set_id is not None else "global"
    if document_id is not None and db.get(Document, document_id) is None:
        raise AdvisorDocumentNotFoundError("Document not found.")
    if document_id is None and document_set_id is not None and db.get(DocumentSet, document_set_id) is None:
        raise AdvisorDocumentNotFoundError("Document set not found.")

    results = search_similar_chunks(
        query=question,
        db=db,
        top_k=top_k,
        source_type=source_type,
        classification=classification,
        document_id=document_id,
        document_set_id=document_set_id,
    )
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
    citations = _build_advisor_citations(results, question)

    if not results:
        return AdvisorAskResponse(
            question=question,
            answer="I do not have enough retrieved evidence to answer this question.",
            citations=[],
            confidence="low",
            limitations=["No relevant source chunks were retrieved."],
            scope=scope,
            document_id=document_id,
            document_set_id=document_set_id,
        )

    provider = get_llm_provider()
    llm_response = provider.answer_question(
        question=question,
        sources=source_contexts,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=build_user_prompt(question, source_contexts),
    )

    limitations = llm_response.limitations or []
    return AdvisorAskResponse(
        question=question,
        answer=llm_response.answer,
        citations=citations,
        confidence=llm_response.confidence,  # type: ignore[arg-type]
        limitations=limitations,
        scope=scope,
        document_id=document_id,
        document_set_id=document_set_id,
    )


def generate_board_summary(
    document_id: UUID | None,
    summary_type: SummaryType,
    top_k: int,
    db: Session,
    document_set_id: UUID | None = None,
) -> BoardSummaryResponse:
    if document_id is not None:
        return _generate_document_board_summary(document_id=document_id, summary_type=summary_type, top_k=top_k, db=db)

    if document_set_id is None:
        raise AdvisorValidationError("Either document_id or document_set_id is required.")

    document_set = db.get(DocumentSet, document_set_id)
    if document_set is None:
        raise AdvisorDocumentNotFoundError("Document set not found.")

    results = _retrieve_set_summary_chunks(document_set=document_set, summary_type=summary_type, top_k=top_k, db=db)
    if not results:
        raise AdvisorValidationError("Document set has no chunks to summarize.")

    return _build_board_summary_response(
        results=results,
        summary_type=summary_type,
        document_set_id=document_set.id,
        scope="document_set",
    )


def _generate_document_board_summary(
    document_id: UUID,
    summary_type: SummaryType,
    top_k: int,
    db: Session,
) -> BoardSummaryResponse:
    document = db.get(Document, document_id)
    if document is None:
        raise AdvisorDocumentNotFoundError("Document not found.")

    if document.status not in {"chunked", "embedded", "indexed"}:
        raise AdvisorValidationError("Document must be chunked or embedded before board summary generation.")

    results = _retrieve_summary_chunks(document=document, summary_type=summary_type, top_k=top_k, db=db)
    if not results:
        raise AdvisorValidationError("Document has no chunks to summarize.")

    return _build_board_summary_response(
        results=results,
        summary_type=summary_type,
        document_id=document.id,
        scope="document",
    )


def _build_board_summary_response(
    results: list[SearchResult],
    summary_type: SummaryType,
    scope: str,
    document_id: UUID | None = None,
    document_set_id: UUID | None = None,
) -> BoardSummaryResponse:

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
    citations = _build_citations(results, SUMMARY_TYPE_QUERIES[summary_type])

    provider = get_llm_provider()
    llm_response = provider.generate_board_summary(
        summary_type=summary_type,
        sources=source_contexts,
        system_prompt=BOARD_SUMMARY_SYSTEM_PROMPT,
        user_prompt=build_board_summary_prompt(summary_type, source_contexts),
    )

    return BoardSummaryResponse(
        document_id=document_id,
        document_set_id=document_set_id,
        scope=scope,  # type: ignore[arg-type]
        summary_type=summary_type,
        memo=BoardMemo(
            executive_summary=llm_response.executive_summary,
            key_risks=llm_response.key_risks,
            evidence=llm_response.evidence,
            board_questions=llm_response.board_questions,
            recommended_actions=llm_response.recommended_actions,
            limitations=llm_response.limitations,
        ),
        citations=citations,
        confidence=llm_response.confidence,  # type: ignore[arg-type]
    )


def _retrieve_summary_chunks(
    document: Document,
    summary_type: str,
    top_k: int,
    db: Session,
) -> list[SearchResult]:
    if document.status in {"embedded", "indexed"}:
        try:
            results = search_similar_chunks(
                query=SUMMARY_TYPE_QUERIES[summary_type],
                db=db,
                top_k=top_k,
                document_id=document.id,
            )
        except Exception:
            results = []

        if results:
            return results

    return _load_ordered_chunks(document=document, top_k=top_k, db=db)


def _retrieve_set_summary_chunks(
    document_set: DocumentSet,
    summary_type: str,
    top_k: int,
    db: Session,
) -> list[SearchResult]:
    try:
        results = search_similar_chunks(
            query=SUMMARY_TYPE_QUERIES[summary_type],
            db=db,
            top_k=top_k,
            document_set_id=document_set.id,
        )
    except Exception:
        results = []

    if results:
        return results

    return _load_ordered_chunks_for_set(document_set=document_set, top_k=top_k, db=db)


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


def _is_useful_chunk(chunk: DocumentChunk) -> bool:
    normalized = " ".join(chunk.content.split())
    if not normalized:
        return False
    return not bool((chunk.chunk_metadata or {}).get("low_value")) and not is_low_value_chunk(normalized)


def _build_advisor_citations(results: list[SearchResult], query: str) -> list[AdvisorCitation]:
    return [
        AdvisorCitation(
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
        for index, result in enumerate(results, start=1)
        for excerpt in [_excerpt_for_result(result, query)]
    ]


def _build_citations(results: list[SearchResult], query: str) -> list[Citation]:
    return [
        Citation(
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
        for index, result in enumerate(results, start=1)
        for excerpt in [_excerpt_for_result(result, query)]
    ]


def _excerpt_for_result(result: SearchResult, query: str) -> str:
    return extract_relevant_excerpt(result.content, query, max_chars=500)
