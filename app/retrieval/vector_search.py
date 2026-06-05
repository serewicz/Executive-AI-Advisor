from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.embedder import embed_texts
from app.models.document import Document, DocumentChunk


@dataclass(frozen=True)
class SearchResult:
    document_id: UUID
    document_title: str
    chunk_id: UUID
    chunk_index: int
    content: str
    page_start: int
    page_end: int
    similarity_score: float
    source_type: str
    classification: str


def search_similar_chunks(
    query: str,
    db: Session,
    top_k: int = 5,
    source_type: str | None = None,
    classification: str | None = None,
) -> list[SearchResult]:
    normalized_query = " ".join(query.split())
    if not normalized_query:
        raise ValueError("Search query cannot be empty.")

    query_embedding = embed_texts([normalized_query])[0]
    cosine_distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("cosine_distance")

    statement = (
        select(DocumentChunk, Document, cosine_distance)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(cosine_distance)
        .limit(top_k)
    )

    if source_type is not None:
        statement = statement.where(Document.source_type == source_type)
    if classification is not None:
        statement = statement.where(Document.classification == classification)

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
            similarity_score=round(max(0.0, min(1.0, 1 - float(distance))), 6),
            source_type=document.source_type,
            classification=document.classification,
        )
        for chunk, document, distance in rows
    ]
