from sqlalchemy.orm import Session

from app.advisor.prompts import SYSTEM_PROMPT, build_user_prompt
from app.advisor.providers.base import SourceContext
from app.advisor.providers.factory import get_llm_provider
from app.advisor.schemas import AdvisorAskResponse, AdvisorCitation
from app.retrieval.vector_search import search_similar_chunks


def answer_executive_question(
    question: str,
    db: Session,
    top_k: int = 5,
    source_type: str | None = None,
    classification: str | None = None,
) -> AdvisorAskResponse:
    results = search_similar_chunks(
        query=question,
        db=db,
        top_k=top_k,
        source_type=source_type,
        classification=classification,
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
    citations = [
        AdvisorCitation(
            document_id=result.document_id,
            document_title=result.document_title,
            chunk_id=result.chunk_id,
            page_start=result.page_start,
            page_end=result.page_end,
            excerpt=result.content[:1000],
        )
        for result in results
    ]

    if not results:
        return AdvisorAskResponse(
            question=question,
            answer="I do not have enough retrieved evidence to answer this question.",
            citations=[],
            confidence="low",
            limitations=["No relevant source chunks were retrieved."],
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
    )
